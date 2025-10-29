from pydantic import BaseModel, Field
from datetime import datetime as dt
from typing import Optional

class ExpenseOpponentBase(BaseModel):
    name: str = Field(..., description="Name of the expense opponent")
    type: str = Field(..., description="Type of expense opponent (e.g., individual, company)")
    description: str = Field(..., description="Description of the expense opponent")
    paymentNumber: str = Field(..., description="Payment number associated with the expense opponent")
    npwp: Optional[str] = Field(None, description="NPWP number")

class ExpenseOpponentCreate(ExpenseOpponentBase):
    pass

class ExpenseOpponentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    paymentNumber: Optional[str] = None
    npwp: Optional[str] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[dt] = None

class ExpenseOpponentResponse(ExpenseOpponentBase):
    id: int
    createdAt: dt
    createdBy: int
    updatedAt: Optional[dt] = None
    updatedBy: Optional[int] = None
    isDelete: bool
    deletedAt: Optional[dt] = None
    deletedBy: Optional[int] = None

    class Config:
        from_attributes = True

class ExpenseOpponentListResponse(BaseModel):
    data: list[ExpenseOpponentResponse]
    count: int