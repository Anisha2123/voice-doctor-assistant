import { useCallback, useEffect, useRef, useState } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { audioContext, chime, endTone, ringStart, ringStop } from "./sounds.js";

const BARS = 28;

/** Call lifecycle, live transcript and audio levels. status: idle | connecting | live | ended */
export function useCall() {
  const [status, setStatus] = useState("idle");
  const [lines, setLines] = useState([]); // {role: "user"|"bot", text, final}
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [startedAt, setStartedAt] = useState(0);
  const client = useRef(null);
  const audio = useRef(null);
  const analysers = useRef([]);
  const finished = useRef(true);

  useEffect(() => {
    if (status !== "live") return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [status]);

  const push = (role, text, final = true) =>
    setLines((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === role && (role === "bot" || !last.final)) {
        const joined = role === "bot" ? `${last.text} ${text}` : text;
        return [...prev.slice(0, -1), { role, text: joined, final }];
      }
      return [...prev, { role, text, final }];
    });

  const attach = (track) => {
    const c = audioContext();
    const an = c.createAnalyser();
    an.fftSize = 256;
    c.createMediaStreamSource(new MediaStream([track])).connect(an);
    analysers.current.push(an);
  };

  // Loudest of mic + agent, folded into BARS bands. Read by the waveform each animation frame.
  const getBars = useCallback(() => {
    const out = new Array(BARS).fill(0);
    for (const an of analysers.current) {
      const d = new Uint8Array(an.frequencyBinCount);
      an.getByteFrequencyData(d);
      const per = Math.floor(d.length * 0.6 / BARS) || 1; // voice sits in the lower bins
      for (let i = 0; i < BARS; i++) {
        let s = 0;
        for (let k = 0; k < per; k++) s += d[i * per + k];
        out[i] = Math.max(out[i], s / per / 255);
      }
    }
    return out;
  }, []);

  const finish = useCallback(() => {
    ringStop();
    if (!finished.current) { finished.current = true; endTone(); }
    analysers.current = [];
    setStatus("ended");
  }, []);

  const start = useCallback(async () => {
    setError(""); setLines([]); setSeconds(0); setMuted(false);
    setStartedAt(Date.now()); setStatus("connecting");
    finished.current = false; analysers.current = [];
    audioContext().resume?.();
    ringStart();
    audio.current = audio.current || new Audio();
    const c = new PipecatClient({
      transport: new SmallWebRTCTransport({ waitForICEGathering: true }),
      enableMic: true,
      enableCam: false,
      callbacks: {
        onBotReady: () => { ringStop(); chime(); setStatus("live"); },
        onUserTranscript: (d) => d.text?.trim() && push("user", d.text.trim(), d.final),
        onBotTranscript: (d) => d.text?.trim() && push("bot", d.text.trim()),
        onTrackStarted: (track, p) => {
          if (track.kind !== "audio") return;
          attach(track);
          if (!p?.local) {
            audio.current.srcObject = new MediaStream([track]);
            audio.current.play().catch(() => {});
          }
        },
        onDisconnected: () => { if (!finished.current) finish(); },
        onError: () => setError("Connection problem. Check the backend is running."),
      },
    });
    client.current = c;
    try {
      await c.connect({ webrtcRequestParams: { endpoint: "/api/offer" } });
    } catch {
      ringStop(); finished.current = true;
      setError("Could not start the call. Is the backend running and the microphone allowed?");
      setStatus("idle");
    }
  }, [finish]);

  const end = useCallback(async () => {
    try { await client.current?.disconnect(); } catch {}
    finish();
  }, [finish]);

  const toggleMute = useCallback(() => {
    setMuted((m) => { client.current?.enableMic(m); return !m; });
  }, []);

  return { status, lines, muted, seconds, error, startedAt, start, end, toggleMute, getBars };
}
