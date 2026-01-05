from datetime import datetime as dt
from sqlalchemy import Table, Column, Integer, Boolean, DateTime, Float, String
from utils.database import metadata

interpayment_table = Table(
    "interpayments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bankAccountIDOrigin", Integer(), nullable=False),
    Column("bankAccountIDDestination", Integer(), nullable=False),
    Column("amount", Float(), nullable=False),
    Column("description", String, nullable=False),
    Column("date", DateTime(), default=dt.now, nullable=False),
    Column("isDelete", Boolean(), default=False, nullable=False),
    Column("createdBy", Integer(), nullable=False),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("deletedBy", Integer(), nullable=True),
    Column("deletedAt", DateTime(), default=None, onupdate=dt.now, nullable=True)
)