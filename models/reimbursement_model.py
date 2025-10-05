from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey
from utils.database import metadata
from datetime import datetime

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
    Column("isApprove", Boolean(), nullable=False, default=False),
    Column("approvedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("approvedAt", DateTime(), nullable=True, default=None),
    Column("createdAt", DateTime(), nullable=False, default=datetime.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
)

reimbursement_items_table = Table(
    "reimbursement_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reimbursementID", Integer, ForeignKey("reimbursements.id"), nullable=False),
    Column("description", String(100), nullable=False),
    Column("amount", Float(), nullable=False),
    Column("date", Date(), nullable=False),
)