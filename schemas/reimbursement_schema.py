from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date as d, datetime

class ReimbursementItemsBase(BaseModel):
    description: str
    amount: float = Field(ge=0)
    date: d

class ReimbursementItemsCreate(ReimbursementItemsBase):
    pass

class ReimbursementItems(ReimbursementItemsBase):
    id: int
    reimbursementID: int

    class Config:
        from_attributes = True

class ReimbursementBase(BaseModel):
    date: d
    dueDate: d
    projectName: str
    purchaseType: str
    bankName: str
    bankAccountName: str
    bankAccountNumber: str
    paymentMethod: str

class ReimbursementCreate(ReimbursementBase):
    reimbursementItems: List[ReimbursementItemsCreate]

class ReimbursementUpdate(BaseModel):
    isPaid: Optional[bool] = None
    isDelete: Optional[bool] = None
    isApprove: Optional[bool] = None

class Reimbursement(ReimbursementBase):
    id: int
    name: Optional[str] = None
    isPaid: bool = False
    isDelete: bool = False
    isApprove: bool = False
    approvedBy: Optional[int] = None
    approvedAt: Optional[datetime] = None
    createdAt: datetime
    createdBy: Optional[int] = None
    updatedAt: Optional[datetime] = None
    updatedBy: Optional[int] = None
    deletedAt: Optional[datetime] = None
    deletedBy: Optional[int] = None
    reimbursementItems: List[ReimbursementItems] = []

    class Config:
        from_attributes = True

class ReimbursementWithAmount(Reimbursement):
    amount: Optional[float] = None

class ReimbursementResponse(BaseModel):
    message: str
    reimbursementID: int
    name: str

class ReimbursementListResponse(BaseModel):
    data: List[ReimbursementWithAmount]
    count: int

class ReimbursementDetailResponse(BaseModel):
    reimbursement: Reimbursement
    reimbursement_items: List[ReimbursementItems]
    payments: List