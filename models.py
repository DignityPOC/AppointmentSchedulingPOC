from pydantic import BaseModel
from typing import Optional

class Patient(BaseModel):
    id: Optional[str] = None  # Id should be set at the API or DB level
    first_name: str
    last_name: str
    email: str
    date_of_birth: str
    gender: str
    phone_number: str
    address: Optional[str] = None