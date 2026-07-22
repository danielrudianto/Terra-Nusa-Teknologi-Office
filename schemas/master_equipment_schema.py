from pydantic import BaseModel, StringConstraints, ConfigDict
from typing import Annotated, Optional
from datetime import datetime as dt


class MasterEquipmentBase(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    category: Annotated[str, StringConstraints(min_length=1, max_length=45)]
    capacity: Annotated[str, StringConstraints(max_length=45)] | None = None
    brand: Annotated[str, StringConstraints(max_length=45)] | None = None
    description: str | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=45)] = "hari"


class MasterEquipmentCreate(MasterEquipmentBase):
    createdBy: int | None = None


class MasterEquipmentUpdate(BaseModel):
    id: int
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    category: Annotated[str, StringConstraints(min_length=1, max_length=45)] | None = None
    capacity: Annotated[str, StringConstraints(max_length=45)] | None = None
    brand: Annotated[str, StringConstraints(max_length=45)] | None = None
    description: str | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=45)] | None = None
    updatedBy: int | None = None


class MasterEquipmentResponse(MasterEquipmentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    createdBy: int | None = None
    createdAt: dt | None = None
    updatedBy: int | None = None
    updatedAt: dt | None = None
    deletedBy: int | None = None
    deletedAt: dt | None = None
    isDelete: bool = False


class MasterEquipmentSearchDocument(BaseModel):
    id: int
    name: str
    category: str
    capacity: Optional[str] = ""
    brand: Optional[str] = ""
    unit: Optional[str] = "hari"