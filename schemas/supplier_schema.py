from pydantic import BaseModel, EmailStr, StringConstraints, field_validator, ConfigDict
from typing import Annotated, Optional
from datetime import datetime as dt

class SupplierBase(BaseModel):
    prefix: Annotated[str, StringConstraints(min_length=1, max_length=25)] | None = None
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    phoneNumber: Annotated[str, StringConstraints(pattern=r"^[0-9]{10,20}$")]
    email: Annotated[EmailStr, StringConstraints(max_length=255)] | None = None
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None
    itemsSold: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    serviceArea: Annotated[str, StringConstraints(min_length=1, max_length=255)]

class SupplierCreate(SupplierBase):
    createdBy: int | None = None

class SupplierUpdate(SupplierBase):
    id: int
    updatedBy: int | None = None

class SupplierResponse(SupplierBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    createdBy: int | None = None
    createdAt: dt | None = None
    updatedBy: int | None = None
    updatedAt: dt | None = None
    deletedAt: dt | None = None
    deletedBy: int | None = None
    isDelete: bool = False

class SupplierSearchDocument(BaseModel):
    id: int
    name: str
    address: str
    city: str
    province: str
    phoneNumber: str
    email: Optional[str] = None
    npwp: Optional[str] = None
    itemsSold: list[str]
    serviceArea: list[str]