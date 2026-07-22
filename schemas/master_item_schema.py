from pydantic import BaseModel, StringConstraints, ConfigDict
from typing import Annotated, Optional, List
from datetime import datetime as dt


class MasterItemBase(BaseModel):
    sku: Annotated[str, StringConstraints(min_length=1, max_length=45)]
    description: Annotated[str, StringConstraints(min_length=1)]
    brand: Annotated[str, StringConstraints(min_length=1, max_length=45)]
    type: Annotated[str, StringConstraints(min_length=1, max_length=45)]
    unit: Annotated[str, StringConstraints(min_length=1, max_length=45)]
    availablePurchaseType: Annotated[str, StringConstraints(max_length=100)] | None = None


class MasterItemCreate(MasterItemBase):
    createdBy: int | None = None


class MasterItemUpdate(BaseModel):
    id: int
    sku: Annotated[str, StringConstraints(min_length=1, max_length=45)] | None = None
    description: Annotated[str, StringConstraints(min_length=1)] | None = None
    brand: Annotated[str, StringConstraints(min_length=1, max_length=45)] | None = None
    type: Annotated[str, StringConstraints(min_length=1, max_length=45)] | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=45)] | None = None
    availablePurchaseType: Annotated[str, StringConstraints(max_length=100)] | None = None
    updatedBy: int | None = None


class MasterItemResponse(MasterItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    createdBy: int | None = None
    createdAt: dt | None = None
    updatedBy: int | None = None
    updatedAt: dt | None = None
    deletedAt: dt | None = None
    deletedBy: int | None = None
    isDelete: bool = False


class MasterItemSearchDocument(BaseModel):
    id: int
    sku: str
    description: str
    brand: str
    type: str
    unit: str
    availablePurchaseType: List[str] = []


class ImportRowError(BaseModel):
    row: int
    sku: Optional[str] = None
    reason: str


class ImportResult(BaseModel):
    inserted: int
    skipped_duplicates: int
    failed: int
    errors: List[ImportRowError] = []