# Pipeline description

Edit this in your own words before submitting. Facts below are what the code actually does.

The browser opens a WebRTC connection to a FastAPI server, which starts a Pipecat pipeline for that call.
Mic audio goes through Silero VAD to find when the caller stops talking, then to ElevenLabs realtime STT.
The transcript goes to Gemini 2.5 Flash, which has three registered functions: check availability, book, cancel.
Gemini's reply is spoken by ElevenLabs TTS (Flash model) and streamed back to the browser.

The tools read and write an in-memory store. Phone numbers are normalised to 10 digits in the tool, and the
system prompt forces the agent to read the number back and get a "yes" first. Double bookings are rejected by the tool.
When a booking or cancellation happens, the server pushes an event over SSE, so the dashboard refreshes and highlights the row.
Transcript events come from Pipecat's RTVI messages. I chose Gemini because of its free quota.
