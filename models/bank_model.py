from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float
from utils.database import metadata
from datetime import date as d
from datetime import datetime as dt

# Define the Purchase model
class BankAccount(BaseModel):
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    isDelete: bool = False  # Flag to indicate if the purchase is deleted

# Define the SQLAlchemy table
bank_accounts_table = Table(
    "bank_accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False, unique=True, index=True,),
    Column("isDelete", Boolean(), default=False, nullable=False),
    Column("createdBy", Integer(), nullable=False),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("updatedBy", Integer(), nullable=True),
    Column("updatedAt", DateTime(), default=None, onupdate=dt.now, nullable=True),
    Column("deletedBy", Integer(), nullable=True),
    Column("deletedAt", DateTime(), default=None, onupdate=dt.now, nullable=True)
)
    