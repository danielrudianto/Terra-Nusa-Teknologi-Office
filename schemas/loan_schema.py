from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class LoanBase(BaseModel):
    date: date
    creditorName: str
    creditorAddress: str
    creditorNPWP: Optional[str] = None
    description: str
    received: float = Field(ge=0)
    debt: float = Field(ge=0)
    bankAccountName: str
    bankAccountNumber: str
    bankName: str
    # rekening perusahaan tujuan penerimaan dana (dari bank_accounts)
    bankAccountID: Optional[int] = None

class LoanCreate(LoanBase):
    pass

class LoanResponse(LoanBase):
    id: int
    isPaid: bool = False
    createdBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[datetime] = None

class LoanListResponse(BaseModel):
    data: list
    count: int

class CreateLoanResponse(BaseModel):
    message: str
    loan_id: int

class LoanPaymentsResponse(BaseModel):
    loan: dict
    payments: list

class ErrorResponse(BaseModel):
    error: str
    status: int