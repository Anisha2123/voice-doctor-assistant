import { useEffect, useRef } from "react";

const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const fmtDay = (d) => new Date(d + "T00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });

function Waveform({ getBars, active }) {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current, g = cv.getContext("2d");
    let raf, smooth = [];
    const draw = () => {
      const w = cv.width, h = cv.height, bars = active ? getBars() : [];
      g.clearRect(0, 0, w, h);
      const n = 28, gap = 4, bw = (w - gap * (n - 1)) / n;
      g.fillStyle = getComputedStyle(cv).color;
      for (let i = 0; i < n; i++) {
        const target = Math.min(1, (bars[i] || 0) * 1.6);
        smooth[i] = (smooth[i] || 0) * 0.7 + target * 0.3;
        const bh = Math.max(4, smooth[i] * h);
        g.beginPath();
        g.roundRect(i * (bw + gap), (h - bh) / 2, bw, bh, bw / 2);
        g.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [getBars, active]);
  return <canvas ref={ref} width={300} height={64} className="wave" />;
}

function Card({ ev }) {
  const a = ev.appointment, booked = ev.type === "booked";
  return (
    <div className={`confirm ${booked ? "ok" : "gone"}`} key={ev.n}>
      <span className="tick">{booked ? "✓" : "✕"}</span>
      <div>
        <b>{booked ? "Appointment confirmed" : "Appointment cancelled"}</b>
        <p>{a.doctor_name} · {a.speciality}</p>
        <p>{fmtDay(a.date)}, {a.time_label}</p>
        <small>{a.id} · {a.phone}</small>
      </div>
    </div>
  );
}

export default function Phone({ call, event, onClose }) {
  const { status, lines, muted, seconds } = call;
  const scroll = useRef(null);
  useEffect(() => { scroll.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [lines, event]);
  const sub = { connecting: "Calling…", live: fmtTime(seconds), ended: `Call ended · ${fmtTime(seconds)}`, idle: "" }[status];

  return (
    <div className="backdrop" onClick={status === "ended" ? onClose : undefined}>
      <div className={`phone ${status}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Call">
        <div className="notch" />
        <div className="who-block">
          <div className="avatar">
            <span className="ring r1" /><span className="ring r2" />CC
          </div>
          <h3>City Care Clinic</h3>
          <p className="sub mono">{sub}</p>
        </div>

        <Waveform getBars={call.getBars} active={status === "live"} />

        <div className="p-transcript" ref={scroll}>
          {lines.slice(-6).map((l, i) => (
            <p key={i} className={`bub ${l.role} ${l.final ? "" : "interim"}`}>{l.text}</p>
          ))}
          {event && <Card ev={event} />}
        </div>

        <div className="p-controls">
          {status === "ended" ? (
            <>
              <button className="p-btn text" onClick={onClose}>Close</button>
              <button className="p-btn call" onClick={call.start} aria-label="Call again">↻</button>
            </>
          ) : (
            <>
              <button className={`p-btn ${muted ? "on" : ""}`} onClick={call.toggleMute} disabled={status !== "live"} aria-label="Mute">
                {muted ? "Unmute" : "Mute"}
              </button>
              <button className="p-btn end" onClick={call.end} aria-label="End call">✕</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
