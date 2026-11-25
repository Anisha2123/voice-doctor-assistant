"""Run: python test_tools.py  (no API keys needed)"""
import asyncio
import data

def ok(c, m): print(("PASS " if c else "FAIL ") + m); assert c

r = data.check_availability("cardiology", None)
d = r["result"][0]; s = d["slots"][0]
ok(d["doctor"].startswith("Dr. Ananya"), "check by speciality")
ok("error" in data.check_availability("dentist", None), "unknown speciality -> error")
ok(data.normalize_phone("+91 98765-43210") == "9876543210", "phone normalisation (+91)")
ok(data.normalize_phone("12345") is None, "short number rejected")
q = data.subscribe()
b = data.book("98765 43210", d["doctor_id"], s["slot_id"])
ok(b.get("status") == "booked", "book")
ok(q.get_nowait()["type"] == "booked", "booked event published")
ok("taken" in data.book("9999999999", d["doctor_id"], s["slot_id"])["error"], "double booking blocked")
ok(len(data.list_appointments()) == 1, "appointment listed")
ok("error" in data.cancel("1111111111"), "cancel unknown number -> error")
c = data.cancel("+919876543210")
ok(c.get("status") == "cancelled", "cancel by phone")
ok(q.get_nowait()["type"] == "cancelled", "cancelled event published")
ok(data.check_availability("cardiology", None)["result"][0]["slots"][0]["slot_id"] == s["slot_id"], "slot freed after cancel")
print("ALL PASS")
