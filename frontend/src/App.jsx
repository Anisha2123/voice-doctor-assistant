import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useCall } from "./useCall.js";
import Phone from "./Phone.jsx";

const fmtDay = (d) => new Date(d + "T00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const j = (u) => fetch(u).then((r) => r.json());

function useClinic() {
  const [doctors, setDoctors] = useState([]);
  const [appts, setAppts] = useState([]);
  const [flash, setFlash] = useState(null); // {slot, appt, kind}
  const [last, setLast] = useState(null); // last booking/cancel event, kept for the phone card
  const load = useCallback(async () => {
    const [d, a] = await Promise.all([j("/api/doctors"), j("/api/appointments")]);
    setDoctors(d); setAppts(a);
  }, []);
  useEffect(() => {
    load().catch(() => {});
    const es = new EventSource("/api/events");
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      load();
      if (ev.type !== "reset") {
        setLast({ ...ev, n: Date.now() });
        setFlash({ slot: ev.slot_id, appt: ev.appointment.id, kind: ev.type, n: Date.now() });
        setTimeout(() => setFlash(null), 3500);
      }
    };
    return () => es.close();
  }, [load]);
  return { doctors, appts, flash, last };
}

function Transcript({ lines, status }) {
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [lines]);
  return (
    <div className="transcript">
      {lines.length === 0 && (
        <p className="empty">{status === "live" ? "Listening…" : "The conversation appears here."}</p>
      )}
      {lines.map((l, i) => (
        <div key={i} className={`msg ${l.role} ${l.final ? "" : "interim"}`}>
          <span className="who">{l.role === "bot" ? "Agent" : "Caller"}</span>
          <p>{l.text}</p>
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}

export default function App() {
  const call = useCall();
  const { doctors, appts, flash, last } = useClinic();
  const [phone, setPhone] = useState(false);
  const tryCall = () => { setPhone(true); call.start(); };
  const days = useMemo(() => [...new Set(doctors.flatMap((d) => d.slots.map((s) => s.date)))].sort(), [doctors]);
  const [day, setDay] = useState(null);
  const activeDay = day || days[0];
  const live = call.status === "live";
  const busy = call.status === "connecting";

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="mark" />City Care <em>Voice Desk</em></div>
        <div className={`pill ${call.status}`}>
          <i />{{ idle: "Ready", connecting: "Connecting", live: `Live · ${fmtTime(call.seconds)}`, ended: "Call ended" }[call.status]}
        </div>
      </header>

      <main>
        <section className="card call">
          <div className="card-head">
            <h2>Call</h2>
            <div className="actions">
              {live && (
                <button className="ghost" onClick={call.toggleMute}>{call.muted ? "Unmute" : "Mute"}</button>
              )}
              {live || busy ? (
                <button className="danger" onClick={() => { call.end(); }}>End call</button>
              ) : (
                <button className="primary" onClick={tryCall}>Try call</button>
              )}
            </div>
          </div>
          {call.error && <p className="err">{call.error}</p>}
          <Transcript lines={call.lines} status={call.status} />
        </section>

        <section className="card appts">
          <div className="card-head"><h2>Appointments</h2><span className="count">{appts.length}</span></div>
          {appts.length === 0 ? (
            <p className="empty">No appointments yet.</p>
          ) : (
            <table>
              <thead><tr><th>Patient</th><th>Doctor</th><th>When</th></tr></thead>
              <tbody>
                {appts.map((a) => (
                  <tr key={a.id} className={flash?.appt === a.id ? "hl" : ""}>
                    <td className="mono">{a.phone}</td>
                    <td>{a.doctor_name}<small>{a.speciality}</small></td>
                    <td>{fmtDay(a.date)}<small>{a.time_label}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {flash?.kind === "cancelled" && <p className="toast">Appointment cancelled</p>}
          {flash?.kind === "booked" && <p className="toast ok">Appointment booked</p>}
        </section>

        <section className="card docs">
          <div className="card-head">
            <h2>Doctors</h2>
            <div className="days">
              {days.map((d) => (
                <button key={d} className={d === activeDay ? "on" : ""} onClick={() => setDay(d)}>{fmtDay(d)}</button>
              ))}
            </div>
          </div>
          <div className="doc-grid">
            {doctors.map((d) => (
              <article key={d.id}>
                <h3>{d.name}</h3>
                <p>{d.speciality}</p>
                <div className="slots">
                  {d.slots.filter((s) => s.date === activeDay).map((s) => (
                    <span key={s.id} className={`slot ${s.booked ? "taken" : ""} ${flash?.slot === s.id ? "hl" : ""}`}>{s.time_label}</span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
      {phone && call.status !== "idle" && (
        <Phone call={{ ...call, start: tryCall }} event={last && last.n > call.startedAt ? last : null} onClose={() => setPhone(false)} />
      )}
    </div>
  );
}
