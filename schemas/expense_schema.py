from pydantic import BaseModel, Field
from datetime import date as d, datetime as dt
from typing import Optional

class ExpenseBase(BaseModel):
    invoiceName: str = Field(..., description="Name of the invoice")
    receiptName: str = Field(..., description="Name of the receipt")
    opponentID: Optional[int] = Field(None, description="ID of the opponent")
    date: d = Field(..., description="Date of the expense")
    dueDate: Optional[d] = Field(None, description="Due date of the expense")
    purchaseType: str = Field(..., description="Type of the purchase")
    dpp: float = Field(..., ge=0, description="DPP value")
    pbbkb: float = Field(..., ge=0, description="PBBKB value")
    pphCode: Optional[str] = Field(None, description="PPH code")
    pphTaxObject: Optional[str] = Field(None, description="PPH tax object")
    pphPercentage: float = Field(..., ge=0, le=16, description="PPH percentage")
    bankName: str = Field(..., description="Name of the bank")
    bankAccountName: str = Field(..., description="Name of the bank account")
    bankAccountNumber: str = Field(..., description="Bank account number")
    paymentMethod: str = Field(..., description="Payment method")
    description: str = Field(..., description="Description of the expense")

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(BaseModel):
    invoiceName: Optional[str] = None
    receiptName: Optional[str] = None
    opponentID: Optional[int] = None
    date: Optional[d] = None
    dueDate: Optional[d] = None
    purchaseType: Optional[str] = None
    dpp: Optional[float] = None
    pbbkb: Optional[float] = None
    pphCode: Optional[str] = None
    pphTaxObject: Optional[str] = None
    pphPercentage: Optional[float] = None
    bankName: Optional[str] = None
    bankAccountName: Optional[str] = None
    bankAccountNumber: Optional[str] = None
    paymentMethod: Optional[str] = None
    description: Optional[str] = None
    isPaid: Optional[bool] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[dt] = None

class ExpenseResponse(ExpenseBase):
    id: int
    isPaid: bool
    isDelete: bool
    createdAt: dt
    updatedAt: Optional[dt] = None
    deletedAt: Optional[dt] = None
    createdBy: int
    updatedBy: Optional[int] = None
    deletedBy: Optional[int] = None
    opponentName: Optional[str] = None

    class Config:
        from_attributes = True

class ExpenseListResponse(BaseModel):
    data: list[ExpenseResponse]
    count: int

class ExpenseFilter(BaseModel):
    isDue: bool = False
    isNotDue: bool = False
    isPaid: bool = False
    isUnpaid: bool = False