from fastapi import FastAPI, HTTPException, status

from DB.database_connection_appointments import AppointmentManager
from graph_logic import build_graph
from schedule_appointment import build_appointment_graph
from cancel_appointment import build_cancel_appointment_graph
from gemini_graph import build_gemini_graph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages import BaseMessage
from pydantic import parse_obj_as, BaseModel
from typing import List, Optional, Literal
from models import Patient, PatientVerificationByPhone, PatientVerificationBySsn, Appointment, UpdateAppointment, ViewAppointmentReq

app = FastAPI()
graph = build_graph()
schedule_graph = build_appointment_graph()
cancel_schedule_graph = build_cancel_appointment_graph()
gemini_graph = build_gemini_graph()
# Doing in-memory storage
patients_db: List[Patient] = []
patients: []
patient: Patient

class ChatMessage(BaseModel):
    role: Literal["user", "ai", "human", "assistant"]
    content: str


class Req(BaseModel):
    input_text: str
    messages: Optional[List[ChatMessage]] = None


class Req(BaseModel):
    input_text: str
    messages: Optional[List[dict]] = None


class ScheduleReq(BaseModel):
    patient_name: str
    doctor_name: str
    date: str
    time: str
    
class CancelScheduleReq(BaseModel):
    emailId: str


@app.post("/process-input")
def process(req: Req):
    initial_state = {"input_text": req.input_text}
    final_state = graph.invoke(initial_state)
    return {"result": final_state["output"]}


@app.post("/ScheduleAppointment")
def ScheduleAppointment(req: ScheduleReq):
    manager = AppointmentManager()
    return manager.schedule_appointment(req.patient_name, req.doctor_name, req.date, req.time)

@app.post("/CancelAppointment")
def CancelAppointment(req: ScheduleReq):
    manager = AppointmentManager()
    return manager.cancel_appointment(req)

@app.post("/RescheduleAppointment")
def RescheduleAppointment(req: UpdateAppointment):
    manager = AppointmentManager()
    return manager.reschedule_appointment(req.patient_name, req.doctor_name, req.new_appointment_date, req.new_appointment_time)

@app.get("/appointments/", response_model=List[Appointment])
async def get_all_appointments():
    """
    Retrieves a list of all registered patients.
    """
    manager = AppointmentManager()
    return manager.view_appointments()
