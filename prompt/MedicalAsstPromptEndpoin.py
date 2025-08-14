import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from langchain.chat_models import AzureChatOpenAI
from langchain.schema import HumanMessage

OPENAI_API_KEY = ""
OPENAI_API_BASE = ""
DEPLOYMENT_NAME = "gpt-4o-mini"
OPENAI_API_VERSION = "2024-12-01-preview"

llm = AzureChatOpenAI(
    deployment_name=DEPLOYMENT_NAME,
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_API_BASE,
    openai_api_version=OPENAI_API_VERSION,
    temperature=0
)

app = FastAPI(title="AI Appointment Assistant (POC)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, Dict[str, Any]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # session_id from client


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    done: bool = False
    missing_slots: Optional[List[str]] = None
    tool_result: Optional[str] = None

def new_session() -> str:
    """Create and return a new session id and initial state."""
    sid = str(uuid.uuid4())
    sessions[sid] = {
        "slots": {
            "name": None,
            "doctor": None,
            "date": None,
            "time": None,
            "appointment_id": None,
        },
        "allAppointmentsSlots": {
            "name": None,
            "doctor": None,
            "date": None,
            "time": None,
            "appointment_id": None,
        },
        "action": None,
        "history": [],
        "appointments": [],
        "intent": None
    }
    return sid

def get_session(session_id: Optional[str]) -> (str, Dict[str, Any]):
    """Return existing session or create a new one."""
    if not session_id or session_id not in sessions:
        sid = new_session()
        return sid, sessions[sid]
    return session_id, sessions[session_id]

def tool_schedule(session_state: Dict[str, Any]) -> str:
    """Schedule appointment: stores appointment in session_state['appointments']"""
    slots = session_state["slots"]
    apt_id = f"apt-{int(datetime.utcnow().timestamp())}"
    apt = {
        "id": apt_id,
        "name": slots["name"],
        "doctor": slots["doctor"],
        "date": slots["date"],
        "time": slots["time"],
        "created_at": datetime.utcnow().isoformat(),
    }
    session_state["appointments"].append(apt)
    print("Appointments", session_state["appointments"]);
    return f"Scheduled: {apt['id']} with Dr. {apt['doctor']} on {apt['date']} at {apt['time']} for {apt['name']}."

def tool_reschedule(session_state: Dict[str, Any]) -> str:
    """Reschedule appointment by appointment_id; if appointment_id missing, try to match by details."""
    slots = session_state["slots"]
    apt_id = slots.get("appointment_id")
    if not apt_id:
        return "No appointment id provided to reschedule."

    for apt in session_state["appointments"]:
        if apt["id"] == apt_id:
            apt["date"] = slots.get("date") or apt["date"]
            apt["time"] = slots.get("time") or apt["time"]
            return f"Rescheduled {apt_id} to {apt['date']} at {apt['time']}."
    return f"Appointment {apt_id} not found."

def tool_cancel(session_state: Dict[str, Any]) -> str:
    """Cancel appointment by appointment_id."""
    slots = session_state["slots"]
    apt_id = slots.get("appointment_id")
    if not apt_id:
        return "No appointment id provided to cancel."

    for i, apt in enumerate(session_state["appointments"]):
        if apt["id"] == apt_id:
            session_state["appointments"].pop(i)
            return f"Cancelled appointment {apt_id}."
    return f"Appointment {apt_id} not found."

def tool_view(session_state: Dict[str, Any]) -> str:
    """View appointments optionally filtered by slots (doctor/date/name)."""
    slots = session_state["allAppointmentsSlots"]
    results = []
    for apt in session_state["appointments"]:
        match = True

        if slots.get("doctor"):
            apt_doctors = apt["doctor"] if isinstance(apt["doctor"], list) else [apt["doctor"]]
            slot_doctors = slots["doctor"] if isinstance(slots["doctor"], list) else [slots["doctor"]]
            if not any(ad.lower() == sd.lower() for ad in apt_doctors for sd in slot_doctors):
                match = False

        if slots.get("date"):
            apt_dates = apt["date"] if isinstance(apt["date"], list) else [apt["date"]]
            slot_dates = slots["date"] if isinstance(slots["date"], list) else [slots["date"]]
            if not any(str(ad) == str(sd) for ad in apt_dates for sd in slot_dates):
                match = False

        if slots.get("name"):
            slot_names = slots["name"] if isinstance(slots["name"], list) else [slots["name"]]
            if not any(sn.lower() in apt["name"].lower() for sn in slot_names):
                match = False

        if match:
            results.append(
                f"{apt['id']}: Dr. {', '.join(apt_doctors)} on {', '.join(apt_dates)} at {', '.join(apt['time'] if isinstance(apt['time'], list) else [apt['time']])} for {apt['name']}"
            )

    if not results:
        return "No appointments found matching your criteria."
    return "\n".join(results)


TOOLS = {
    "schedule": tool_schedule,
    "reschedule": tool_reschedule,
    "cancel": tool_cancel,
    "view": tool_view,
}

EXTRACTION_PROMPT = """
You are a JSON extractor for an appointment assistant.  
Given the session ID, the user's latest message, and prior conversation history,  
return a JSON with exactly two keys: "intent" and "slots".

- "intent" should be one of: "schedule", "reschedule", "cancel", "view", or "none".
  Use "none" if the message is just a greeting or unrelated.

- "slots" is an object with the keys: "name", "doctor", "date", "time", "appointment_id".
  If a field is not present in the latest message, try to extract it from the conversation history.
  If it is still unknown, set it to null.

- Always preserve previously mentioned information from history (e.g., if the name was already given earlier in the conversation, include it again in the output).

Input:
Session ID: {session_id}

Conversation history (most recent last):
{history}

User message:
\"\"\"{message}\"\"\"

Return ONLY valid JSON (no extra commentary or text outside the JSON).
Example output:
{{"intent": "schedule", "slots": {{"name": "Krishna", "doctor": "Dr. Smith", "date": "2024-08-01", "time": "15:00", "appointment_id": null}}}}
"""


def call_llm_extract(payload: Dict[str, Any], history: List[str]) -> Dict[str, Any]:
    user_message = payload.get("message", "").strip()
    session_id = payload.get("session_id", "")

    history_text = "\n".join(history[-10:])

    prompt = EXTRACTION_PROMPT.format(
        session_id=session_id,
        history=history_text,
        message=user_message
    )

    response = llm([HumanMessage(content=prompt)])
    text = response.content.strip()

    try:
        data = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        try:
            data = json.loads(text[start:end + 1])
        except Exception:
            data = {
                "intent": "none",
                "slots": {
                    "name": None,
                    "doctor": None,
                    "date": None,
                    "time": None,
                    "appointment_id": None
                }
            }

    data.setdefault("slots", {})
    for k in ["name", "doctor", "date", "time", "appointment_id"]:
        data["slots"].setdefault(k, None)

    return data

REQUIRED_SLOTS = {
    "schedule": ["name", "doctor", "date", "time"],
    "reschedule": ["appointment_id", "date", "time"],
    "cancel": ["appointment_id"],
    "view": [],
}

def determine_missing_slots(action: str, slots: Dict[str, Optional[str]]) -> List[str]:
    """Return list of missing required slots for given action."""
    required = REQUIRED_SLOTS.get(action, [])
    missing = [s for s in required if not slots.get(s)]
    return missing

def llm_finalize_message(user_message: str, action: str, tool_result: Optional[str], slots: Dict[str, Any]) -> str:
    """
    Use LLM to compose a nice final message summarizing the action and tool result.
    """
    prompt = f"""
You are a friendly assistant. The user said: "{user_message}"
The action performed: "{action}"
Slots collected: {json.dumps(slots)}
Tool result: "{tool_result}"

Please return a polite one-paragraph final message to the user confirming the result.
Do not summarize or skip any items from the tool result. 
List all appointments exactly as they appear above.
"""
    resp = llm([HumanMessage(content=prompt)])
    return resp.content.strip()

@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):

    session_id, state = get_session(payload.session_id)

    state["history"].append(f"User: {payload.message}")
    print(session_id)


    low = payload.message.strip().lower()
    if low in ("hi", "hello", "hey", "good morning", "good afternoon"):
        reply = "Hello! I can help you schedule, reschedule, cancel, or view appointments. What would you like to do?"
        state["history"].append(f"Bot: {reply}")
        return ChatResponse(session_id=session_id, reply=reply, done=False, missing_slots=[])


    extraction = call_llm_extract(
        {
            "message": payload.message,
            "session_id": session_id
        },
        state["history"]
    )
    intent = extraction["intent"]
    extracted_slots = extraction["slots"]
    print("intent", intent)
    print("extracted_slots", extracted_slots)


    if intent == "none" and all(value is None for value in extracted_slots.values()):
        reply = ("I can help you with appointments (schedule / reschedule / cancel / view). "
                 "Which one would you like to do?")
        state["history"].append(f"Bot: {reply}")
        return ChatResponse(session_id=session_id, reply=reply, done=False, missing_slots=[])
    if intent == "none" and any(value is not None for value in extracted_slots.values()):
        intent = state["intent"]
        print("INTENT", intent)

    state["action"] = intent
    state["intent"] = intent
    if state["intent"] == "reschedule":
        extracted_slots["date"] = None
        extracted_slots["time"] = None

    for k, v in extracted_slots.items():
        if not v:
            continue

        value = v.strip() if isinstance(v, str) else v

        if k in state["allAppointmentsSlots"] and state["allAppointmentsSlots"][k]:
            if isinstance(state["allAppointmentsSlots"][k], list):
                if value not in state["allAppointmentsSlots"][k]:
                    state["allAppointmentsSlots"][k].append(value)
            else:
                if state["allAppointmentsSlots"][k] != value:
                    state["allAppointmentsSlots"][k] = [state["allAppointmentsSlots"][k], value]
        else:
            state["allAppointmentsSlots"][k] = value

        for k, v in extracted_slots.items():
            if v:
                state["slots"][k] = v.strip() if isinstance(v, str) else v

    missing = determine_missing_slots(state["action"], state["slots"])

    if missing:
        next_slot = missing[0]
        if next_slot == "name":
            question = "Sure — what's your full name?"
        elif next_slot == "doctor":
            question = "Which doctor or provider would you like to see?"
        elif next_slot == "date":
            question = "Which date would you prefer? (please use YYYY-MM-DD)"
        elif next_slot == "time":
            question = "What time do you prefer? (e.g., 15:00)"
        elif next_slot == "appointment_id":
            question = "Please provide the appointment id (e.g., apt-123) for the appointment."
        else:
            question = f"Please provide {next_slot}."

        state["history"].append(f"Bot: {question}")
        return ChatResponse(session_id=session_id, reply=question, done=False, missing_slots=missing)

    action = state["action"]
    tool_func = TOOLS.get(action)
    if not tool_func:
        reply = "Sorry, I could not find the tool to perform that action."
        state["history"].append(f"Bot: {reply}")
        return ChatResponse(session_id=session_id, reply=reply, done=False)

    tool_result = tool_func(state)

    final_msg = llm_finalize_message(payload.message, action, tool_result, state["slots"])

    state["history"].append(f"Bot: {final_msg}")
    return ChatResponse(session_id=session_id, reply=final_msg, done=True, missing_slots=[], tool_result=tool_result)

@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    """Return current session state (for debugging only; do not expose in production)."""
    return sessions.get(session_id, {"error": "session not found"})

@app.get("/hello")
def hello():
    return {"message": "Appointment Flow Service running."}
