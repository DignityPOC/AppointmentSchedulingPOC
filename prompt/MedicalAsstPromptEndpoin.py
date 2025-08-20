import uuid
import json
import re
from dateutil import parser as dtparser
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
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
    if not session_id or session_id not in sessions:
        sid = new_session()
        return sid, sessions[sid]
    return session_id, sessions[session_id]

def tool_schedule(session_state: Dict[str, Any]) -> str:
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
    slots = session_state["allAppointmentsSlots"]
    results = []

    for apt in session_state["appointments"]:
        match = True
        if slots.get("doctor"):
            apt_doctors = apt["doctor"] if isinstance(apt["doctor"], list) else [apt["doctor"]]
            slot_doctors = slots["doctor"] if isinstance(slots["doctor"], list) else [slots["doctor"]]
            if not any(ad.lower() == sd.lower() for ad in apt_doctors for sd in slot_doctors):
                match = False
        else:
            apt_doctors = apt["doctor"] if isinstance(apt["doctor"], list) else [apt["doctor"]]

        if slots.get("date"):
            apt_dates = apt["date"] if isinstance(apt["date"], list) else [apt["date"]]
            slot_dates = slots["date"] if isinstance(slots["date"], list) else [slots["date"]]
            if not any(str(ad) == str(sd) for ad in apt_dates for sd in slot_dates):
                match = False
        else:
            apt_dates = apt["date"] if isinstance(apt["date"], list) else [apt["date"]]

        if slots.get("name"):
            slot_names = slots["name"] if isinstance(slots["name"], list) else [slots["name"]]
            if not any(sn.lower() in apt["name"].lower() for sn in slot_names):
                match = False

        if match:
            apt_times = apt["time"] if isinstance(apt["time"], list) else [apt["time"]]
            results.append(
                f"{apt['id']}: Dr. {', '.join(apt_doctors)} on {', '.join(apt_dates)} at {', '.join(apt_times)} for {apt['name']}"
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

- "intent" must be one of: "schedule", "reschedule", "cancel", "view", or "none".
  Use "none" if the message is a greeting or unrelated.

- "slots" is an object with the keys: "name", "doctor", "date", "time", "appointment_id".
  If a field is not present in the latest message, try to extract it from the conversation history.
  If unknown, set it to null.

- Always preserve previously mentioned information from history (e.g., if the name was already given earlier, include it again in the output).

Disambiguation rules:
- If the latest message contains phrases like "meet/see/with <Name>", treat <Name> as the doctor/provider, unless the message also contains "my name is".
- Do not carry over a previous doctor if a new doctor-like name appears in the latest message; prefer the latest message.

Input:
Session ID: {session_id}

Conversation history (most recent last):
{history}

User message:
\"\"\"{message}\"\"\"

Return ONLY valid JSON (no commentary outside JSON).
Example output:
{{"intent": "schedule", "slots": {{"name": "Krishna", "doctor": "Dr. Smith", "date": "2024-08-01", "time": "15:00", "appointment_id": null}}}}
"""

FOLLOWUP_PROMPT = """
You are a conversational assistant collecting required details to complete an appointment action.

Return ONLY valid JSON with exactly these keys: "missing", "next_slot", "question".
- "missing": array of the required slot names that are still missing (e.g., ["name","doctor"])
- "next_slot": one slot name from the missing list you intend to ask next, or null if none missing
- "question": a single short, friendly follow-up question tailored to collect "next_slot".

Rules:
- If no required slots are missing, set "next_slot" to null and "question" to "".
- Be concise and polite. Do not output anything except the JSON.

Context:
intent: {intent}
required_slots: {required_slots}
known_slots: {known_slots}
conversation_history (most recent last):
{history}
"""

def llm_next_question(intent: str, required_slots: list, known_slots: dict, history: list) -> dict:
    history_text = "\n".join(history[-10:])
    compact_known = {k: v for k, v in known_slots.items() if v not in [None, "", [], {}]}

    prompt = FOLLOWUP_PROMPT.format(
        intent=intent,
        required_slots=required_slots or [],
        known_slots=compact_known,
        history=history_text
    )
    resp = llm([HumanMessage(content=prompt)])
    raw = resp.content.strip()

    try:
        data = json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        try:
            data = json.loads(raw[start:end+1])
        except Exception:
            data = {"missing": [], "next_slot": None, "question": ""}

    data.setdefault("missing", [])
    data.setdefault("next_slot", None)
    data.setdefault("question", "")
    if not isinstance(data["missing"], list):
        data["missing"] = []
    if not isinstance(data["question"], str):
        data["question"] = ""
    return data


WELCOME_PROMPT = """
You are a friendly appointment assistant. The user greeted you or gave an unclear message.
Reply with one short paragraph (<=2 sentences) that says hello and explains you can help with
scheduling, rescheduling, canceling, or viewing appointments. Ask what they'd like to do.
Return only the reply text.
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

USER_TZ = ZoneInfo("America/New_York")  # e.g., EST/EDT

def parse_date_time_from_text(text: str) -> dict | None:
    default_dt = datetime.now(USER_TZ).replace(month=1, day=1, hour=9, minute=0, second=0, microsecond=0)
    try:
        dt = dtparser.parse(text, default=default_dt, fuzzy=True)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=USER_TZ)

    mentioned_year = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if not mentioned_year:
        dt = dt.replace(year=datetime.now(USER_TZ).year)

    return {
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M"),
        "aware_dt": dt
    }


def is_past(aware_dt: datetime) -> bool:
    now = datetime.now(aware_dt.tzinfo or USER_TZ)
    return aware_dt < now

def postprocess_extracted_slots(extracted: dict, state: dict, user_msg: str) -> dict:
    slots = dict(extracted)

    name_phrase = re.search(r"(?:\bmy\s+name\s+is\b|\bi am\b)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", user_msg, re.I)
    if name_phrase:
        slots["name"] = name_phrase.group(1)

    doc_phrase = re.search(r"\b(?:meet|see|with)\s+(Dr\.?\s*)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", user_msg, re.I)
    if doc_phrase:
        doctor_name = doc_phrase.group(2)
        if not (slots.get("name") and slots["name"] == doctor_name):
            slots["doctor"] = doctor_name

    if slots.get("name") and slots.get("doctor") and slots["name"] == slots["doctor"]:
        prior_name = state["slots"].get("name")
        if prior_name and prior_name != slots["name"]:
            slots["name"] = prior_name
        else:
            slots["name"] = None

    user_has_explicit_year = bool(re.search(r"\b(19|20)\d{2}\b", user_msg))

    dt_parts = parse_date_time_from_text(user_msg)
    if dt_parts:
        if not slots.get("date"):
            slots["date"] = dt_parts["date"]
        if not slots.get("time"):
            slots["time"] = dt_parts["time"]

    if slots.get("date") and not user_has_explicit_year:
        try:
            base = dtparser.parse(slots["date"], default=datetime.now(ZoneInfo("America/New_York")))
            normalized = base.replace(year=datetime.now(ZoneInfo("America/New_York")).year)
            slots["date"] = normalized.date().isoformat()
        except Exception:
            pass

    aware_dt = None
    if dt_parts and dt_parts.get("aware_dt"):
        aware_dt = dt_parts["aware_dt"]
    elif slots.get("date") and slots.get("time"):
        try:
            tmp = dtparser.parse(
                f"{slots['date']} {slots['time']}",
                default=datetime.now(ZoneInfo("America/New_York"))
            )
            if tmp.tzinfo is None:
                tmp = tmp.replace(tzinfo=ZoneInfo("America/New_York"))
            aware_dt = tmp
        except Exception:
            aware_dt = None

    if aware_dt:
        slots["_aware_dt"] = aware_dt

    return slots


REQUIRED_SLOTS = {
    "schedule": ["name", "doctor", "date", "time"],
    "reschedule": ["appointment_id", "date", "time"],
    "cancel": ["appointment_id"],
    "view": [],
}

def determine_missing_slots(action: str, slots: Dict[str, Optional[str]]) -> List[str]:
    required = REQUIRED_SLOTS.get(action, [])
    missing = [s for s in required if not slots.get(s)]
    return missing

def llm_finalize_message(user_message: str, action: str, tool_result: Optional[str], slots: Dict[str, Any]) -> str:
    safe_slots = {k: v for k, v in slots.items() if not str(k).startswith("_")}
    try:
        slots_json = json.dumps(safe_slots)
    except TypeError:
        def _coerce(o):
            if isinstance(o, datetime):
                return o.isoformat()
            return str(o)
        slots_json = json.dumps(safe_slots, default=_coerce)

    prompt = f"""
You are a friendly assistant. The user said: "{user_message}"
The action performed: "{action}"
Slots collected: {slots_json}
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

    extraction = call_llm_extract(
        {"message": payload.message, "session_id": session_id},
        state["history"]
    )
    intent = extraction.get("intent", "none")
    extracted_slots = postprocess_extracted_slots(extraction["slots"], state, payload.message)

    aware_dt = extracted_slots.pop("_aware_dt", None)
    if not aware_dt and state["slots"].get("date") and state["slots"].get("time"):
        try:
            aware_dt = dtparser.parse(
                f"{state['slots']['date']} {state['slots']['time']}",
                default=datetime.now(USER_TZ)
            )
            if aware_dt.tzinfo is None:
                aware_dt = aware_dt.replace(tzinfo=USER_TZ)
        except Exception:
            aware_dt = None

    if aware_dt and is_past(aware_dt):
        ask_future = (
            "That time appears to be in the past. "
            "Please share a future date and time (e.g., 2025-09-02 17:00 or Sep 2 at 5 PM)."
        )
        state["history"].append(f"Bot: {ask_future}")
        return ChatResponse(session_id=session_id, reply=ask_future, done=False, missing_slots=["date", "time"])

    if intent == "none" and any(v not in [None, "", [], {}] for v in extracted_slots.values()):
        intent = state.get("intent") or intent

    if intent == "none" and all(v in [None, "", [], {}] for v in extracted_slots.values()):
        welcome = llm([HumanMessage(content=WELCOME_PROMPT)]).content.strip()
        state["history"].append(f"Bot: {welcome}")
        return ChatResponse(session_id=session_id, reply=welcome, done=False, missing_slots=[])

    state["action"] = intent
    state["intent"] = intent

    if state["intent"] == "reschedule":
        extracted_slots["date"] = None
        extracted_slots["time"] = None

    for k, v in extracted_slots.items():
        if not v or k.startswith("_"):
            continue
        value = v.strip() if isinstance(v, str) else v
        if k in state["allAppointmentsSlots"] and state["allAppointmentsSlots"][k]:
            if isinstance(state["allAppointmentsSlots"][k], list):
                if isinstance(value, list):
                    for vv in value:
                        if vv not in state["allAppointmentsSlots"][k]:
                            state["allAppointmentsSlots"][k].append(vv)
                else:
                    if value not in state["allAppointmentsSlots"][k]:
                        state["allAppointmentsSlots"][k].append(value)
            else:
                if state["allAppointmentsSlots"][k] != value:
                    state["allAppointmentsSlots"][k] = [state["allAppointmentsSlots"][k]]
                    if isinstance(value, list):
                        for vv in value:
                            if vv not in state["allAppointmentsSlots"][k]:
                                state["allAppointmentsSlots"][k].append(vv)
                    else:
                        state["allAppointmentsSlots"][k].append(value)
        else:
            state["allAppointmentsSlots"][k] = value

    for k, v in extracted_slots.items():
        if v and not k.startswith("_"):
            state["slots"][k] = v.strip() if isinstance(v, str) else v

    required = REQUIRED_SLOTS.get(state["action"], [])
    followup = llm_next_question(
        intent=state["action"],
        required_slots=required,
        known_slots=state["slots"],
        history=state["history"]
    )
    missing = followup.get("missing", [])
    next_slot = followup.get("next_slot")
    question = followup.get("question", "")

    if next_slot:
        state["history"].append(f"Bot: {question}")
        return ChatResponse(session_id=session_id, reply=question, done=False, missing_slots=missing)

    action = state["action"]
    tool_func = TOOLS.get(action)
    if not tool_func:
        reply = "Sorry, I couldn’t find the tool to perform that action."
        state["history"].append(f"Bot: {reply}")
        return ChatResponse(session_id=session_id, reply=reply, done=False)

    tool_result = tool_func(state)

    final_msg = llm_finalize_message(payload.message, action, tool_result, state["slots"])
    state["history"].append(f"Bot: {final_msg}")

    return ChatResponse(session_id=session_id, reply=final_msg, done=True, missing_slots=[], tool_result=tool_result)

@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="session not found")
    return jsonable_encoder(state)

@app.get("/hello")
def hello():
    return {"message": "Appointment Flow Service running."}
