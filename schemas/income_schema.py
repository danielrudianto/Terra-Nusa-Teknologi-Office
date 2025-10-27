from pydantic import BaseModel, Field
from datetime import date as d, datetime as dt
from typing import Optional

class IncomeBase(BaseModel):
    amount: float = Field(..., title="Amount of the income")
    date: d = Field(..., title="Date of the income")
    incomeType: str = Field(..., title="Income type")
    opponentID: int = Field(..., title="Opponent ID", ge=1)
    description: Optional[str] = Field(default=None, title="Description of the income")

class IncomeCreate(IncomeBase):
    createdBy: int
    createdAt: dt = Field(default_factory=dt.now)

class IncomeUpdate(BaseModel):
    amount: Optional[float] = None
    date: Optional[d] = None
    incomeType: Optional[str] = None
    opponentID: Optional[int] = None
    description: Optional[str] = None

class IncomeResponse(IncomeBase):
    id: int
    isDelete: bool = False
    createdBy: int
    createdAt: dt
    deletedBy: Optional[int] = None
    deletedAt: Optional[dt] = None
    opponentName: Optional[str] = None

    class Config:
        from_attributes = True

class IncomeListResponse(BaseModel):
    data: list[IncomeResponse]
    count: int