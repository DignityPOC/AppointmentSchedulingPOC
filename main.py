from fastapi import FastAPI, HTTPException, status

from DB.database_connection import AppointmentAndPatientManager
from graph_logic import build_graph
from schedule_appointment import build_appointment_graph
from cancel_appointment import build_cancel_appointment_graph
from gemini_graph import build_gemini_graph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages import BaseMessage
from pydantic import parse_obj_as, BaseModel
from typing import List, Optional, Literal
from models import Patient, PatientVerificationByPhone, CancelAppointmentReq, PatientVerificationBySsn, Appointment, UpdateAppointment, Provider

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
    patient_id: int
    provider_id: int
    date: str
    time: str

class ScheduleAppointmentRequestWithDetails(BaseModel):
    first_name: str
    last_name: str
    gender: str
    dob: str
    email: str
    phone_number: str
    address: str
    provider_id: int
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
    manager = AppointmentAndPatientManager()
    return manager.schedule_appointment(req.patient_id, req.provider_id, req.date, req.time)

@app.post("/ScheduleAppointmentWithDetails")
def ScheduleAppointmentWithDetails(req: ScheduleAppointmentRequestWithDetails):
    manager = AppointmentAndPatientManager()
    return manager.schedule_appointment_with_detail(req)

@app.post("/CancelAppointmentById")
def CancelAppointment(req: int):
    manager = AppointmentAndPatientManager()
    return manager.cancel_appointment_by_id(req)

@app.post("/CancelAppointment")
def CancelAppointment(req: CancelAppointmentReq):
    manager = AppointmentAndPatientManager()
    return manager.cancel_appointment(req)

@app.post("/RescheduleAppointment")
def RescheduleAppointment(req: UpdateAppointment):
    manager = AppointmentAndPatientManager()
    return manager.reschedule_appointment(req.provider_name, req.patient_first_name, req.patient_last_name, req.new_appointment_date, req.new_appointment_time)

@app.post("/patients/", response_model=Patient, status_code=status.HTTP_201_CREATED)
async def register_patient(patient: Patient):
    """
    Registers a new patient.
    """
    manager = AppointmentAndPatientManager()
    manager.add_patient(patient.first_name, patient.last_name, patient.gender, patient.date_of_birth,
                        patient.email, patient.phone_number, patient.address)
    return patient

@app.get("/patients/", response_model=List[Patient])
async def get_all_patients():
    """
    Retrieves a list of all registered patients.
    """
    manager = AppointmentAndPatientManager()
    return manager.get_all_patients()

@app.get("/providers/", response_model=List[Provider])
async def get_all_providers():
    """
    Retrieves a list of all registered patients.
    """
    manager = AppointmentAndPatientManager()
    return manager.get_all_providers()

@app.get("/providers/{provider_id}", response_model=Provider)
async def get_provider_by_id(provider_id: str):
    """
    Retrieves a single patient by its ID.
    """
    manager = AppointmentAndPatientManager()
    provider = manager.get_provider_by_id(provider_id)
    if provider is not None:
        return provider
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

@app.get("/GetProvidersByLocation/", response_model=List[Provider])
async def get_providers_by_location(location: str):
    """
    Retrieves a list of providers by location.
    """
    manager = AppointmentAndPatientManager()
    return manager.get_providers_by_location(location)

@app.get("/GetProvidersBySpeciality/", response_model=List[Provider])
async def get_all_providers_by_speciality(speciality: str):
    """
    Retrieves a list of all providers by speciality.
    """
    manager = AppointmentAndPatientManager()
    return manager.get_providers_by_speciality(speciality)


@app.get("/appointments/", response_model=List[Appointment])
async def get_appointments_by_patient_name(patient_first_name, patient_last_name):
    """
    Retrieves a list of all registered patients.
    """
    manager = AppointmentAndPatientManager()
    return manager.get_appointments_by_patient_Name(patient_first_name, patient_last_name)

@app.get("/patients/{patient_id}", response_model=Patient)
async def get_patient_by_id(patient_id: str):
    """
    Retrieves a single patient by its ID.
    """
    manager = AppointmentAndPatientManager()
    patient = manager.get_patient_by_id(patient_id)
    if patient is not None:
        return patient
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")


@app.get("/patients/{patient_id}", response_model=Patient)
async def get_patient_by_id(patient_id: str):
    """
    Retrieves a single patient by its ID.
    """
    for patient in patients_db:
        if patient.id == patient_id:
            return patient
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

@app.post("/verify_patient_by_phone_and_dob")
async def verify_patient_by_phone_and_dob(patient_data: PatientVerificationByPhone):
    """
    Verify patient details.
    """
    manager = AppointmentAndPatientManager()
    patient = manager.verify_patient_by_phone_and_dob(patient_data)
    if patient is not None:
        return patient

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Patient not found or details do not match"
    )

"""
@app.post("/verify_patient_by_ssn")
async def verify_patient_by_ssn(patient_data: PatientVerificationBySsn):
    for patient in patients_db:
        if (patient_data.first_name == patient.first_name and
                patient_data.last_name == patient.last_name and
                patient_data.ssn == patient.ssn):
            return {"message": "Patient verified successfully!"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Patient not found or details do not match"
    )
"""

@app.post("/gemini-agent")
def run_gemini_agent(req: Req):
    messages = []

    if req.messages:
        parsed_messages = parse_obj_as(List[ChatMessage], req.messages)
        for m in parsed_messages:
            role = m.role
            if role == "human":
                role = "user"
            elif role == "assistant":
                role = "ai"

            if role == "user":
                messages.append(HumanMessage(content=m.content))
            elif role == "ai":
                messages.append(AIMessage(content=m.content))

    if messages and isinstance(messages[-1], HumanMessage):
        raise ValueError(
            "Cannot append another user message; the last message is already from the user."
        )
    # Always append the latest input_text as a new user message
    messages.append(HumanMessage(content=req.input_text))

    # Validate last message is from user
    if not isinstance(messages[-1], HumanMessage):
        raise ValueError("Gemini requires the last message to be from the user.")

    initial_state = {
        "messages": messages,
        "next": "",
        "query": "",
        "cur_reasoning": "",
        "id_number": "U001",
    }
    final_state = gemini_graph.invoke(initial_state, config={"recursion_limit": 5})
    
        # Only re-invoke if last message is from Human
    if (final_state.get("next") and final_state["next"] != "__end__" and isinstance(final_state["messages"][-1], HumanMessage)):
        final_state = gemini_graph.invoke(final_state, config={"recursion_limit": 5})

    return {
        "messages": [
            {"role": m.type, "content": m.content}
            for m in final_state["messages"]
        ],
        "reasoning": final_state.get("cur_reasoning", ""),
    }