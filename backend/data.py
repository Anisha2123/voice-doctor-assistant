"""In-memory mock clinic data, booking logic and a tiny event bus for live dashboard updates."""
import asyncio
import re
from datetime import date, datetime, timedelta
from itertools import count

DOCTORS = [
    {"id": "d1", "name": "Dr. Ananya Sharma", "speciality": "Cardiology"},
    {"id": "d2", "name": "Dr. Rohan Mehta", "speciality": "Dermatology"},
    {"id": "d3", "name": "Dr. Priya Nair", "speciality": "Pediatrics"},
    {"id": "d4", "name": "Dr. Vikram Rao", "speciality": "Orthopedics"},
    {"id": "d5", "name": "Dr. Sana Iqbal", "speciality": "General Medicine"},
]
TIMES = ["09:00", "09:30", "10:00", "11:00", "12:00", "14:00", "15:00", "16:30", "17:00"]
DAYS_AHEAD = 5

SLOTS: dict[str, dict] = {}
APPOINTMENTS: dict[str, dict] = {}
_ids = count(1)
_subscribers: set[asyncio.Queue] = set()


def _seed():
    SLOTS.clear()
    APPOINTMENTS.clear()
    today = date.today()
    for d in DOCTORS:
        for offset in range(DAYS_AHEAD):
            day = today + timedelta(days=offset)
            if day.weekday() == 6:  # no Sundays
                continue
            for i, t in enumerate(TIMES):
                # deterministic "already taken" slots so the demo isn't all empty
                taken = (int(d["id"][1]) + offset + i) % 4 == 0
                if offset == 0 and t <= datetime.now().strftime("%H:%M"):
                    continue  # past times today
                sid = f'{d["id"]}-{day.isoformat()}-{t}'
                SLOTS[sid] = {"id": sid, "doctor_id": d["id"], "date": day.isoformat(),
                              "time": t, "booked": taken}


_seed()


def label(t: str) -> str:
    return datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0")


def doctor(doctor_id: str):
    return next((d for d in DOCTORS if d["id"] == doctor_id), None)


def normalize_phone(raw: str) -> str | None:
    """Spoken/transcribed number -> 10 digits (strips +91 / leading 0). None if invalid."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def find_doctors(query: str | None):
    if not query:
        return list(DOCTORS)
    q = query.lower().replace("dr.", "").replace("dr ", "").strip()
    return [d for d in DOCTORS if q in d["name"].lower() or q in d["speciality"].lower()
            or d["speciality"].lower() in q or any(p in d["name"].lower() for p in q.split() if len(p) > 2)]


def free_slots(doctor_id: str | None = None, on: str | None = None):
    return sorted(
        (s for s in SLOTS.values()
         if not s["booked"] and (not doctor_id or s["doctor_id"] == doctor_id) and (not on or s["date"] == on)),
        key=lambda s: (s["date"], s["time"]),
    )


def appointment_view(a: dict) -> dict:
    s, d = SLOTS[a["slot_id"]], doctor(a["doctor_id"])
    return {**a, "doctor_name": d["name"], "speciality": d["speciality"], "date": s["date"],
            "time": s["time"], "time_label": label(s["time"])}


def list_appointments():
    return sorted((appointment_view(a) for a in APPOINTMENTS.values()), key=lambda a: (a["date"], a["time"]))


# ---- event bus (consumed by the SSE route in server.py) ----
def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue):
    _subscribers.discard(q)


def publish(event: dict):
    for q in list(_subscribers):
        q.put_nowait(event)


# ---- business operations (return plain dicts the LLM can speak from) ----
def check_availability(doctor_or_speciality: str | None, on: str | None):
    if on:
        try:
            date.fromisoformat(on)
        except ValueError:
            return {"error": "Date must be YYYY-MM-DD."}
    matches = find_doctors(doctor_or_speciality)
    if not matches:
        return {"error": f"No doctor or speciality matches '{doctor_or_speciality}'.",
                "available_doctors": [f'{d["name"]} ({d["speciality"]})' for d in DOCTORS]}
    out = []
    for d in matches:
        slots = free_slots(d["id"], on)[:6]
        out.append({"doctor_id": d["id"], "doctor": d["name"], "speciality": d["speciality"],
                    "slots": [{"slot_id": s["id"], "date": s["date"], "time": label(s["time"])} for s in slots]})
    if not any(x["slots"] for x in out):
        return {"result": out, "note": "No free slots for that request. Offer another date or doctor."}
    return {"result": out}


def book(phone: str, doctor_id: str, slot_id: str):
    p = normalize_phone(phone)
    if not p:
        return {"error": "Invalid phone number. Ask the caller for a 10-digit number."}
    s = SLOTS.get(slot_id)
    if not s or s["doctor_id"] != doctor_id:
        return {"error": "That slot does not exist. Check availability again."}
    if s["booked"]:
        return {"error": "That slot was just taken. Offer another slot."}
    if any(a["phone"] == p and a["slot_id"] == slot_id for a in APPOINTMENTS.values()):
        return {"error": "This caller already has this slot."}
    s["booked"] = True
    aid = f"A{next(_ids):03d}"
    APPOINTMENTS[aid] = {"id": aid, "phone": p, "doctor_id": doctor_id, "slot_id": slot_id,
                         "created_at": datetime.now().isoformat(timespec="seconds")}
    view = appointment_view(APPOINTMENTS[aid])
    publish({"type": "booked", "appointment": view, "slot_id": slot_id})
    return {"status": "booked", "appointment_id": aid, "doctor": view["doctor_name"],
            "date": view["date"], "time": view["time_label"], "phone": p}


def cancel(phone: str, appointment_id: str | None = None):
    p = normalize_phone(phone)
    if not p:
        return {"error": "Invalid phone number. Ask the caller for a 10-digit number."}
    mine = [a for a in APPOINTMENTS.values() if a["phone"] == p]
    if not mine:
        return {"error": "No appointment found for this phone number."}
    if appointment_id:
        mine = [a for a in mine if a["id"] == appointment_id]
        if not mine:
            return {"error": "No such appointment for this number."}
    elif len(mine) > 1:
        return {"error": "Multiple appointments found. Ask which one to cancel.",
                "appointments": [{"appointment_id": a["id"], "doctor": appointment_view(a)["doctor_name"],
                                  "date": appointment_view(a)["date"], "time": appointment_view(a)["time_label"]}
                                 for a in mine]}
    a = mine[0]
    view = appointment_view(a)
    SLOTS[a["slot_id"]]["booked"] = False
    del APPOINTMENTS[a["id"]]
    publish({"type": "cancelled", "appointment": view, "slot_id": a["slot_id"]})
    return {"status": "cancelled", "appointment_id": a["id"], "doctor": view["doctor_name"],
            "date": view["date"], "time": view["time_label"]}
