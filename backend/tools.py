"""The three LLM tools, registered inside the Pipecat pipeline (function calling)."""
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams

import data

check_schema = FunctionSchema(
    name="check_doctor_availability",
    description="List free appointment slots for a doctor or speciality, optionally on one date. "
                "Call with no arguments to list all doctors.",
    properties={
        "doctor_or_speciality": {"type": "string", "description": "Doctor name or speciality, e.g. 'Sharma' or 'cardiology'."},
        "date": {"type": "string", "description": "Optional date in YYYY-MM-DD."},
    },
    required=[],
)
book_schema = FunctionSchema(
    name="book_appointment",
    description="Book a slot for the caller. Only call after the caller confirmed their phone number with an explicit yes.",
    properties={
        "phone": {"type": "string", "description": "Caller's phone number as spoken, digits only."},
        "doctor_id": {"type": "string", "description": "doctor_id from check_doctor_availability."},
        "slot_id": {"type": "string", "description": "slot_id from check_doctor_availability."},
    },
    required=["phone", "doctor_id", "slot_id"],
)
cancel_schema = FunctionSchema(
    name="cancel_appointment",
    description="Cancel the caller's appointment, found by phone number. Only call after the caller confirmed the number with an explicit yes.",
    properties={
        "phone": {"type": "string", "description": "Caller's phone number as spoken, digits only."},
        "appointment_id": {"type": "string", "description": "Only if the caller has several appointments and chose one."},
    },
    required=["phone"],
)

TOOLS = ToolsSchema(standard_tools=[check_schema, book_schema, cancel_schema])


async def check_doctor_availability(params: FunctionCallParams):
    a = params.arguments
    await params.result_callback(data.check_availability(a.get("doctor_or_speciality"), a.get("date")))


async def book_appointment(params: FunctionCallParams):
    a = params.arguments
    await params.result_callback(data.book(a.get("phone", ""), a.get("doctor_id", ""), a.get("slot_id", "")))


async def cancel_appointment(params: FunctionCallParams):
    a = params.arguments
    await params.result_callback(data.cancel(a.get("phone", ""), a.get("appointment_id")))


def register(llm):
    llm.register_function("check_doctor_availability", check_doctor_availability)
    llm.register_function("book_appointment", book_appointment)
    llm.register_function("cancel_appointment", cancel_appointment)
