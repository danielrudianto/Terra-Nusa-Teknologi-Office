from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class PaymentIncomingBase(BaseModel):
    date: date
    amount: float
    salesInvoiceID: Optional[int] = None
    incomeID: Optional[int] = None
    loanID: Optional[int] = None
    bankAccountID: Optional[int] = None
    isApprove: bool = False

class PaymentIncomingCreate(PaymentIncomingBase):
    pass

class PaymentIncomingResponse(PaymentIncomingBase):
    id: int
    isDelete: bool = False
    createdBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaymentCalendarData(BaseModel):
    date: date
    amount: float

class ErrorResponse(BaseModel):
    error: str
    status: int