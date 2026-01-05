from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class InterpaymentBase(BaseModel):
    bankAccountIDOrigin: int = Field(..., title="ID of the origin bank account", ge=1)
    bankAccountIDDestination: int = Field(..., title="ID of the destination bank account", ge=1)
    amount: float = Field(..., title="Amount to be transferred", ge=0)
    date: datetime = Field(default_factory=datetime.now, title="Date of the interpayment")
    description: str = Field("Setoran kas operasional")

class InterpaymentCreate(InterpaymentBase):
    createdBy: Optional[int] = Field(default=None, title="ID of the user who created the interpayment", ge=1)

class InterpaymentResponse(BaseModel):
    id: Optional[int] = Field(default=None, title="ID of the bank account", ge=1)
    bankAccountIDOrigin: int
    bankAccountIDDestination: int
    amount: float
    description: str
    date: datetime
    createdBy: Optional[int] = None
    createdAt: datetime
    isDelete: bool = False
    deletedBy: Optional[int] = None
    deletedAt: Optional[datetime] = None
    originBankName: Optional[str] = None
    originBankAccountName: Optional[str] = None
    originBankAccountNumber: Optional[str] = None
    destinationBankName: Optional[str] = None
    destinationBankAccountName: Optional[str] = None
    destinationBankAccountNumber: Optional[str] = None

class InterpaymentListResponse(BaseModel):
    data: List[InterpaymentResponse]
    count: int

class CreateInterpaymentResponse(BaseModel):
    message: str
    interpaymentID: int

class ErrorResponse(BaseModel):
    error: str
    status: int