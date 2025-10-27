from utils.database import metadata
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey

income_table = Table(
    "income",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("description", String(100), nullable=False),
    Column("date", Date(), nullable=False),
    Column("incomeType", String(100), nullable=False),
    Column("amount", Float(2), nullable=False),
    Column("opponentID", Integer, ForeignKey("expense_opponents.id"), nullable=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
)