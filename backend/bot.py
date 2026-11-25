"""Voice pipeline: caller audio -> STT -> LLM -> TTS -> caller audio."""
import os
from datetime import date

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

from tools import TOOLS, register as register_tools

def system_prompt() -> str:
    return f"""Today is {date.today().strftime("%A, %d %B %Y")} ({date.today().isoformat()}). Use this to turn "tomorrow" or weekdays into YYYY-MM-DD for tools.

You are the receptionist for City Care Clinic. You talk to callers by phone.

Style: warm, brief, natural. One or two short sentences per turn. No lists, no markdown, no emojis. Ask one question at a time.

You can: check doctor availability, book an appointment, cancel an appointment.

Rules:
- The caller is identified ONLY by the phone number they say aloud. Never ask for anything else to identify them.
- Before booking or cancelling, read the phone number back digit by digit and wait for an explicit "yes". If they say no, ask for the number again.
- Never invent doctors, slots or bookings. Only state what the tools return.
- If a tool returns an error, explain it simply and offer an alternative.
- Offer at most three slots at a time, spoken as day and time ("tomorrow at 10 AM").
- Do not read slot IDs or doctor IDs aloud.
- After booking or cancelling, confirm in one sentence and ask if they need anything else."""


async def run_bot(webrtc_connection):
    """Build and run one call."""
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )

    stt = ElevenLabsRealtimeSTTService(api_key=os.environ["ELEVENLABS_API_KEY"])

    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        settings=ElevenLabsTTSService.Settings(
            voice=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
            model="eleven_flash_v2_5",
        ),
    )

    llm = GoogleLLMService(
        api_key=os.environ["GOOGLE_API_KEY"],
        settings=GoogleLLMService.Settings(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            system_instruction=system_prompt(),
        ),
    )
    register_tools(llm)

    context = LLMContext(tools=TOOLS)
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.6)),
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_agg,
            llm,
            tts,
            transport.output(),
            assistant_agg,
        ]
    )
    task = PipelineTask(pipeline)  # RTVI (live transcript events) is added automatically

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        logger.info("Caller connected")
        context.add_message(
            {"role": "user", "content": "A caller just connected. Greet them briefly and ask how you can help."}
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        logger.info("Caller disconnected")
        await task.cancel()

    await WorkerRunner(handle_sigint=False).run(task)
