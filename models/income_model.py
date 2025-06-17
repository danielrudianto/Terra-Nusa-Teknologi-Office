from pydantic import BaseModel, Field
from datetime import date as d

class Income(BaseModel):
    id: int | None = Field(default=None, title="ID of the income", ge=1)
    bankAccountID: int = Field(..., title="ID of the bank account", ge=1)
    amount: float = Field(..., title="Amount of the income")
    date: d = Field(..., title="Date of the income")
    description: str | None = Field(default=None, title="Description of the income")
