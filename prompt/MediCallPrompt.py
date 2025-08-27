# ai_service_medicall.py
import uuid
import json
import re
import os
import types
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from dateutil import parser as dtparser

# Keep the import that works in your env:
from langchain.chat_models import AzureChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from DB.database_connection_appointments import AppointmentManager
from langsmith import traceable

os.environ["LANGSMITH_API_KEY"] = "###"   # <-- put your LangSmith API key here
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "MediCall-POC"

OPENAI_API_KEY = "###"  # <-- put your OpenAI API key here
OPENAI_API_BASE = "###"  # <-- put your OpenAI API base URL here
DEPLOYMENT_NAME = "gpt-4o-mini"
OPENAI_API_VERSION = "2024-12-01-preview"

llm = AzureChatOpenAI(
    deployment_name=DEPLOYMENT_NAME,
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_API_BASE,
    openai_api_version=OPENAI_API_VERSION,
    temperature=0  # deterministic
)

app = FastAPI(title="MediCall Agent Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session state
sessions: Dict[str, Dict[str, Any]] = {}

def new_session() -> str:
    sid = str(uuid.uuid4())
    sessions[sid] = {
        "history": [],
        "appointments": [],
    }
    return sid

def get_session(session_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    if session_id and session_id in sessions:
        return session_id, sessions[session_id]
    sid = new_session()
    return sid, sessions[sid]


# MediCall System Prompt
MEDICALL_PROMPT = """
You are "MediCall," an empathetic and efficient AI medical caller agent. Your job is to help with:
Schedule, Reschedule, Cancel, or View appointments.

TOOLS and REQUIRED PARAMETERS (strict):
1) Tool: ScheduleAppointment
   Parameters: doctorName (string), patientName (string), date (YYYY-MM-DD), time (HH:MM AM/PM)
2) Tool: RescheduleAppointment
   Parameters: doctorName (string), patientName (string),
               oldDate (YYYY-MM-DD), oldTime (HH:MM AM/PM),
               newDate (YYYY-MM-DD), newTime (HH:MM AM/PM)
3) Tool: CancelAppointment
   Parameters: doctorName (string), patientName (string), date (YYYY-MM-DD), time (HH:MM AM/PM)
4) Tool: ViewAppointment
   Parameters: patientName (string), date (optional, YYYY-MM-DD)

INTERACTION PROTOCOL:
1) Greet warmly and state your purpose.
2) Identify intent (schedule, reschedule, cancel, view).
3) Ask polite, concise clarifying questions to gather ALL required parameters.
   - For dates and times: always ask for full, unambiguous values.
     Examples: "August 20, 2025" and "2:30 PM".
4) Confirm the collected information with the patient before using a tool.
5) Once ALL parameters are confirmed for the chosen tool:
   → Output ONLY a single JSON object with the exact structure:

{
  "tool": "<OneOf: ScheduleAppointment | RescheduleAppointment | CancelAppointment | ViewAppointment>",
  "parameters": { "<key>": "<value>", ... }
}

CRITICAL RULES:
- Do NOT add any extra text once you output the JSON.
- If information is incomplete, do NOT output JSON; continue asking questions.
- Be persistent but patient. Keep it short.
"""

#Tools
@traceable(run_type="tool", name="ScheduleAppointment")
def tool_schedule(state: Dict[str, Any], params: Dict[str, str]) -> str:
    manager = AppointmentManager()
    return manager.schedule_appointment(params["patientName"], params["doctorName"], params["date"], params["time"])["Message"]

@traceable(run_type="tool", name="RescheduleAppointment")
def tool_reschedule(state: Dict[str, Any], params: Dict[str, str]) -> str:
            manager = AppointmentManager()
            return manager.reschedule_appointment(params["patientName"].lower(), params["doctorName"].lower(), params["newDate"], params["newTime"])["Message"]

@traceable(run_type="tool", name="CancelAppointment")
def tool_cancel(state: Dict[str, Any], params: Dict[str, str]) -> str:
        requestattr = {
            "patient_name": params["patientName"].lower(),
            "doctor_name": params["doctorName"].lower(),
        }
            # Convert dict into an object with attributes
        request = types.SimpleNamespace(**requestattr)
        manager = AppointmentManager()
        return manager.cancel_appointment(request)["Message"]

@traceable(run_type="tool", name="ViewAppointment")
def tool_view(state: Dict[str, Any], params: Dict[str, str]) -> str:
    name = params["patientName"]
    manager = AppointmentManager()
    hits = manager.view_appointments(name)

    if hits:
        # Convert each Appointment object into a string representation
        formatted_hits = [
            f"- appointment of {appt.patient_name.upper()} with doctor {appt.doctor_name.upper()} on {appt.appointment_date} at {appt.appointment_time}"
            for appt in hits
        ]
        return "Appointments:\n" + "\n".join(formatted_hits)
    else:
        return "No appointment found."


TOOLS = {
    "ScheduleAppointment": tool_schedule,
    "RescheduleAppointment": tool_reschedule,
    "CancelAppointment": tool_cancel,
    "ViewAppointment": tool_view,
}

# Timezone normalization helpers

USER_TZ = ZoneInfo("America/New_York")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s?(AM|PM)$", re.I)

@traceable(run_type="chain", name="normalize_date")
def normalize_date(date_str: str, user_msg: str) -> str:
    """Force current year if user didn't type a 4-digit year in THIS message."""
    user_has_year = bool(re.search(r"\b(19|20)\d{2}\b", user_msg))
    base = dtparser.parse(date_str, default=datetime.now(USER_TZ))
    if not user_has_year:
        base = base.replace(year=datetime.now(USER_TZ).year)
    return base.date().isoformat()  # YYYY-MM-DD


@traceable(run_type="chain", name="normalize_time_ampm")
def normalize_time_ampm(time_str: str) -> str:
    try:
        dt = dtparser.parse(time_str)
        try:
            # Try Unix format first
            return dt.strftime("%-I:%M %p")
        except ValueError:
            # Fallback for Windows
            return dt.strftime("%#I:%M %p")
    except Exception:
        return time_str

@traceable(run_type="chain", name="to_aware")
def to_aware(date_str: str, time_ampm: str) -> datetime:
    dt = dtparser.parse(f"{date_str} {time_ampm}", default=datetime.now(USER_TZ))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=USER_TZ)
    return dt


@traceable(run_type="chain", name="is_past")
def is_past(aware_dt: datetime) -> bool:
    return aware_dt < datetime.now(aware_dt.tzinfo or USER_TZ)


@traceable(run_type="chain", name="extract_json_block")
def extract_json_block(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end+1])
    except Exception:
        return None

@traceable(run_type="chain", name="validate_and_normalize_params")
def validate_and_normalize_params(tool: str, params: Dict[str, Any], user_msg: str) -> Tuple[bool, List[str], Dict[str, str]]:

    errors: List[str] = []
    out: Dict[str, str] = {}

    def need(key: str):
        if not params.get(key):
            errors.append(f"Missing parameter: {key}")

    if tool == "ScheduleAppointment":
        for k in ["doctorName", "patientName", "date", "time"]:
            need(k)
        if errors: return False, errors, out

        out["doctorName"] = str(params["doctorName"]).strip()
        out["patientName"] = str(params["patientName"]).strip()
        out["date"] = normalize_date(str(params["date"]), user_msg)
        out["time"] = normalize_time_ampm(str(params["time"]))

        # Past guard
        if is_past(to_aware(out["date"], out["time"])):
            errors.append("The provided date/time is in the past. Please provide a future date and time.")
            return False, errors, out
        return True, [], out

    if tool == "RescheduleAppointment":
        for k in ["doctorName", "patientName", "oldDate", "oldTime", "newDate", "newTime"]:
            need(k)
        if errors: return False, errors, out

        out["doctorName"] = str(params["doctorName"]).strip()
        out["patientName"] = str(params["patientName"]).strip()
        out["oldDate"] = normalize_date(str(params["oldDate"]), user_msg)
        out["oldTime"] = normalize_time_ampm(str(params["oldTime"]))
        out["newDate"] = normalize_date(str(params["newDate"]), user_msg)
        out["newTime"] = normalize_time_ampm(str(params["newTime"]))

        # Past guard for the new slot
        if is_past(to_aware(out["newDate"], out["newTime"])):
            errors.append("The new date/time is in the past. Please provide a future date and time.")
            return False, errors, out
        return True, [], out

    if tool == "CancelAppointment":
        for k in ["doctorName", "patientName", "date", "time"]:
            need(k)
        if errors: return False, errors, out

        out["doctorName"] = str(params["doctorName"]).strip()
        out["patientName"] = str(params["patientName"]).strip()
        out["date"] = normalize_date(str(params["date"]), user_msg)
        out["time"] = normalize_time_ampm(str(params["time"]))
        return True, [], out

    if tool == "ViewAppointment":
        need("patientName")
        if errors: return False, errors, out
        out["patientName"] = str(params["patientName"]).strip()
        if params.get("date"):
            out["date"] = normalize_date(str(params["date"]), user_msg)
        return True, [], out

    errors.append("Unknown tool.")
    return False, errors, out

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    done: bool = False
    tool_result: Optional[str] = None

@traceable(run_type="chain", name="chat-handler", tags=["api", "chat"])
@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    session_id, state = get_session(payload.session_id)

    messages: List[Any] = [SystemMessage(content=MEDICALL_PROMPT)]
    for turn in state["history"]:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["text"]))
        else:
            messages.append(AIMessage(content=turn["text"]))

    messages.append(HumanMessage(content=payload.message))

    ai = llm(messages)
    text = ai.content.strip()

    json_obj = extract_json_block(text)

    if json_obj and isinstance(json_obj, dict) and "tool" in json_obj and "parameters" in json_obj:
        tool_name = json_obj["tool"]
        raw_params = json_obj["parameters"]

        ok, errs, norm_params = validate_and_normalize_params(tool_name, raw_params, payload.message)
        if not ok:
            error_msg = " ".join(errs)
            assistant_reply = (
                f"{error_msg} Please provide the missing or corrected information."
            )
            state["history"].append({"role": "assistant", "text": assistant_reply})
            state["history"].append({"role": "user", "text": payload.message})
            return ChatResponse(session_id=session_id, reply=assistant_reply, done=False)

        tool_func = TOOLS.get(tool_name)
        if not tool_func:
            assistant_reply = "I recognized your intent, but I can't access that tool."
            state["history"].append({"role": "assistant", "text": assistant_reply})
            state["history"].append({"role": "user", "text": payload.message})
            return ChatResponse(session_id=session_id, reply=assistant_reply, done=False)

        result_text = tool_func(state, norm_params)

        state["history"].append({"role": "assistant", "text": result_text})
        state["history"].append({"role": "user", "text": payload.message})

        return ChatResponse(session_id=session_id, reply=result_text, done=True, tool_result=result_text)

    state["history"].append({"role": "assistant", "text": text})
    state["history"].append({"role": "user", "text": payload.message})
    return ChatResponse(session_id=session_id, reply=text, done=False)

@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="session not found")
    return jsonable_encoder(state)

@app.get("/hello")
def hello():
    return {"message": "MediCall Agent is running."}
