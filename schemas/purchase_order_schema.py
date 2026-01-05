from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date, datetime
from enum import Enum

class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    COMPLETED = "completed"

class PurchaseOrderBase(BaseModel):
    date: date
    supplierID: int
    purchaseType: str
    templateVersion: str
    projectName: str
    dpp: float = Field(ge=0)
    ppn: float = Field(ge=0, default=0.00)
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    customData: Optional[Dict[str, Any]] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    pass

class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    name: str  # Auto-generated name
    createdBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    isDelete: bool = False
    deletedBy: Optional[int] = None
    deletedAt: Optional[datetime] = None

    class Config:
        from_attributes = True

class CreatePurchaseOrderResponse(BaseModel):
    message: str
    purchase_order_id: int
    purchase_order_name: str  # Include the generated name in response

class PurchaseOrderListResponse(BaseModel):
    data: list[PurchaseOrderResponse]
    count: int

class ErrorResponse(BaseModel):
    error: str
    status: int