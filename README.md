# Voice AI Doctor Appointment Assistant

A caller speaks to an AI receptionist that can **check doctor availability**, **book** and **cancel** appointments.
The caller is identified only by the phone number they say aloud, which the agent reads back before booking or cancelling.

**LLM used: Google Gemini (`gemini-2.5-flash`, free tier).** STT and TTS: ElevenLabs. Voice framework: Pipecat. VAD: Silero.

```
browser mic ─WebRTC─▶ Pipecat: ElevenLabs STT ▶ Gemini (+3 tools) ▶ ElevenLabs TTS ─WebRTC─▶ browser speaker
                                         │
                       tools change in-memory data ──SSE──▶ dashboard updates live
```

## Run it

You need Python 3.10+, Node 18+, an [ElevenLabs API key](https://elevenlabs.io) and a [Gemini API key](https://aistudio.google.com/apikey).

**1. Backend** (terminal 1)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # add your two keys
python server.py                                       # http://localhost:7860
```

**2. Frontend** (terminal 2)
```bash
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

Open http://localhost:5173 in Chrome, allow the microphone, click **Try call**.

Try: *"Hi, I'd like to see a cardiologist tomorrow."* → pick a slot → say your 10-digit number → confirm "yes".
Then call again and cancel with the same number. `POST /api/reset` (or restart the server) restores the starting data.

## Project layout
| Path | What it does |
|---|---|
| `backend/bot.py` | Pipecat pipeline, system prompt, VAD |
| `backend/tools.py` | `check_doctor_availability`, `book_appointment`, `cancel_appointment` (function calling) |
| `backend/data.py` | Mock doctors/slots, booking rules, phone normalisation, event bus |
| `backend/server.py` | FastAPI: WebRTC offer, REST routes, SSE `/api/events` |
| `backend/test_tools.py` | Tool-logic tests, no API keys needed (`python test_tools.py`) |
| `frontend/src/useCall.js` | Pipecat JS client: call state, transcript, audio levels |
| `frontend/src/Phone.jsx` | Phone-style call screen, waveform, confirmation card |
| `frontend/src/App.jsx` | Dashboard: transcript, doctors and slots, appointments |

## Notes
- Data is in memory and regenerated on each server start (5 doctors, next 5 days, no Sundays).
- Never commit `.env`; only `.env.example` is tracked.
- Ring, connect and end sounds are synthesised in the browser, so there are no audio assets.
