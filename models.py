from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
import re

class Patient(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    date_of_birth: str
    gender: str
    phone_number: str
    address: Optional[str] = None

class Provider(BaseModel):
    id: int
    provider_name: str
    location: str
    speciality: str
    slots: str

class Appointment(BaseModel):
    id: Optional[int]  # Id should be set at the API or DB level
    patient_name: str
    doctor_name: str
    appointment_date: str
    appointment_time: str

class AppointmentData(BaseModel):
    id: Optional[int]  # Id should be set at the API or DB level
    patient_name: str
    doctor_name: str
    appointment_date: str
    appointment_time: str

class UpdateAppointment(BaseModel):
    provider_name: str
    patient_first_name: str
    patient_last_name: str
    new_appointment_date: str
    new_appointment_time: str

class ViewAppointmentReq(BaseModel):
    patient_name: str

class CancelAppointmentReq(BaseModel):
        first_name: str
        phone_number: str

class PatientVerificationByPhone(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    date_of_birth: date
    phone_number: str

class PatientVerificationBySsn(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    ssn: str = Field(min_length=4, max_length=4)

    # You can add custom validation logic using Pydantic's validator
    @classmethod
    def validate_phone_number(cls, value):
        if not re.match(r"^\+?[1-9]\d{1,14}$", value):
            raise ValueError("Invalid phone number format")
        return value
