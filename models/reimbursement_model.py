from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float
from utils.database import metadata
from datetime import date as d
from datetime import datetime as dt

class ReimbursementItems(BaseModel):
    description: str  # Description of the reimbursement item
    amount : Annotated[float, Field(ge=0)]  # Amount of the reimbursement item (greater than or equal to 0)
    date: d # Date of the reimbursement item

reimbursement_items_table = Table(
    "reimbursement_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reimbursementID", Integer, nullable=False),
    Column("description", String(100), nullable=False),
    Column("amount", Float(), nullable=False),
    Column("date", Date(), nullable=False),
)

# Define the Purchase model
class Reimbursement(BaseModel):
    name: str | None = None# Name of the reimbursement
    date: d  # Date of the reimbursement
    dueDate: d # Due date of the reimbursement
    projectName: str  # Name of the project
    purchaseType: str  # Type of the purchase
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    paymentMethod: str  # Payment method
    isPaid: bool = False  # Flag to indicate if the purchase is paid
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    createdAt: d = Field(default_factory=dt.now)  # Creation date
    createdBy: int | None = None  # ID of the user who created the purchase
    updatedAt: Optional[d] = None  # Update date
    updatedBy: Optional[int] = None  # ID of the user who updated the purchase
    deletedAt: Optional[d] = None  # Deletion date
    deletedBy: Optional[int] = None  # ID of the user who deleted the purchase
    reimbursementItems: Optional[list[ReimbursementItems]] = None  # List of reimbursement items

# Define the SQLAlchemy table
reimbursements_table = Table(
    "reimbursements",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    Column("projectName", String(100), nullable=False),
    Column("purchaseType", String(100), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, nullable=False),
    Column("updatedBy", Integer, nullable=True),
    Column("deletedBy", Integer, nullable=True),
)

