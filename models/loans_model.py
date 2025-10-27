from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey
from utils.database import metadata
from datetime import datetime as dt

# Define the loans table
loans_table = Table(
    "loans",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False),
    Column("creditorName", String, nullable=False),
    Column("creditorAddress", String, nullable=False),
    Column("creditorNPWP", String, default=None, nullable=True),
    Column("description", String, nullable=False, default=""),
    Column("received", Float, nullable=False, default=0),
    Column("debt", Float, nullable=False, default=0),
    Column("bankAccountName", String, nullable=False),
    Column("bankAccountNumber", String, nullable=False),
    Column("bankName", String, nullable=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("isPaid", Boolean(), nullable=False, default=False),
)