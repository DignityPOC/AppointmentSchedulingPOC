from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
import re

class Patient(BaseModel):
    id: Optional[str] = None  # Id should be set at the API or DB level
    first_name: str
    last_name: str
    email: str
    date_of_birth: date
    gender: str
    phone_number: str
    address: Optional[str] = None

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
