from pydantic import BaseModel, EmailStr, StringConstraints, Field
from typing import Annotated
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean, ForeignKey
from utils.database import metadata
from datetime import date as dt

# Define the Client model
class Payment(BaseModel):
    date: dt #Payment date
    amount: float #Payment amount
    paymentMethod: str #Payment method
    purchaseID: int | None = None #Purchase ID
    expenseID: int | None = None #Expense ID
    reimbursementID: int | None = None #Reimbursement ID
    bankAccountID: int | None = None #Bank account ID

# Define the payments table
payments_table = Table(
    "payments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", DateTime(), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("paymentMethod", String(50), nullable=False),
    Column("purchaseID", ForeignKey("purchases.id"), Integer, nullable=True),
    Column("expenseID", Integer, nullable=True),
    Column("reimbursementID", Integer, nullable=True),
    Column("bankAccountID", ForeignKey("bank_accounts.id"), Integer, nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.today()),
    Column("createdBy", ForeignKey("users.id"), Integer, nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None,),
    Column("isDelete", Boolean, default=False),
)
