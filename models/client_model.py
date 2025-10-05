from pydantic import BaseModel, field_validator
from typing import Annotated
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean
from utils.database import metadata
from datetime import datetime as dt
from schemas.client_schema import ClientBase

# Define the clients table
clients_table = Table(
    "clients",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("prefix", String(10), nullable=False, default=""),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(100), nullable=False),
    Column("province", String(100), nullable=False),
    Column("phoneNumber", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(50), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.now),
    Column("createdBy", Integer, nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, nullable=True, default=None),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("deletedBy", Integer, nullable=True, default=None),
)