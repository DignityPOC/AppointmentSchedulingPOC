# backend.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AppointmentRequest(BaseModel):
    patient_name: str
    date: str = None

@app.post("/schedule")
def schedule_appointment(req: AppointmentRequest):
    return {"message": f"Appointment scheduled for {req.patient_name} on {req.date}"}

@app.post("/reschedule")
def reschedule_appointment(req: AppointmentRequest):
    return {"message": f"Appointment rescheduled for {req.patient_name} to {req.date}"}

@app.post("/cancel")
def cancel_appointment(req: AppointmentRequest):
    return {"message": f"Appointment cancelled for {req.patient_name}"}
