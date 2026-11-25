"""FastAPI server: WebRTC signalling for the Pipecat bot (+ REST routes added in part 2)."""
from dotenv import load_dotenv
import asyncio
import json

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(override=True)

from pipecat.transports.smallwebrtc.request_handler import (  # noqa: E402
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

import data  # noqa: E402
from bot import run_bot  # noqa: E402

app = FastAPI(title="Voice Doctor Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
handler = SmallWebRTCRequestHandler()


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/doctors")
async def doctors():
    return [{**d, "slots": [{"id": s["id"], "date": s["date"], "time": s["time"],
                             "time_label": data.label(s["time"]), "booked": s["booked"]}
                            for s in sorted((x for x in data.SLOTS.values() if x["doctor_id"] == d["id"]),
                                            key=lambda x: (x["date"], x["time"]))]}
            for d in data.DOCTORS]


@app.get("/api/appointments")
async def appointments():
    return data.list_appointments()


@app.post("/api/reset")
async def reset():
    data._seed()
    data.publish({"type": "reset"})
    return {"ok": True}


@app.get("/api/events")
async def events():
    """Server-sent events: the dashboard listens here to update live after a booking/cancel."""
    q = data.subscribe()

    async def stream():
        try:
            yield "retry: 1000\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            data.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/offer")
async def offer(request: dict, background: BackgroundTasks):
    async def on_connection(connection):
        background.add_task(run_bot, connection)

    return await handler.handle_web_request(
        request=SmallWebRTCRequest.from_dict(request),
        webrtc_connection_callback=on_connection,
    )


@app.patch("/api/offer")
async def ice_patch(request: dict):
    candidates = [IceCandidate(**c) for c in request["candidates"]]
    await handler.handle_patch_request(
        SmallWebRTCPatchRequest(pc_id=request["pc_id"], candidates=candidates)
    )
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=7860, reload=False)
