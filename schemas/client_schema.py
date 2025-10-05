from pydantic import BaseModel, EmailStr, StringConstraints, ConfigDict, field_validator, Field
from typing import Annotated, Optional
from datetime import datetime as dt

class ClientBase(BaseModel):
    prefix: str = Field(..., description="Prefix for client name (e.g., 'PT', 'CV', 'UD', etc.)")
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    phoneNumber: Annotated[str, StringConstraints(pattern=r"^\+?\d{10,15}$")]
    email: Optional[EmailStr] = None
    npwp: Optional[Annotated[str, StringConstraints(pattern=r"^\d{16}$")]] = None

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, value: str):
        if not value.strip():
            raise ValueError("Prefix cannot be empty")
        return value.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str):
        if not value.strip():
            raise ValueError("Name cannot be empty")
        return value.strip()

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str):
        if not value.strip():
            raise ValueError("Address cannot be empty")
        return value.strip()

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str):
        if not value.strip():
            raise ValueError("City cannot be empty")
        return value.strip()

    @field_validator("province")
    @classmethod
    def validate_province(cls, value: str):
        if not value.strip():
            raise ValueError("Province cannot be empty")
        return value.strip()

    @field_validator("phoneNumber")
    @classmethod
    def validate_phone_number(cls, value: str):
        if not value.strip():
            raise ValueError("Phone number cannot be empty")
        # Remove + if present for validation
        clean_value = value.lstrip('+')
        if not clean_value.isdigit() or len(clean_value) < 10 or len(clean_value) > 15:
            raise ValueError("Phone number must be 10-15 digits")
        return value

class ClientCreate(ClientBase):
    createdBy: Optional[int] = None

class ClientUpdate(ClientBase):
    updatedBy: Optional[int] = None

class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    createdBy: Optional[int] = None
    createdAt: Optional[dt] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[dt] = None
    isDelete: bool = False
    deletedAt: Optional[dt] = None
    deletedBy: Optional[int] = None