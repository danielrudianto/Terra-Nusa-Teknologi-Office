from pydantic import BaseModel, EmailStr, StringConstraints, Field
from typing import Annotated
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean
from utils.database import metadata
from datetime import date

# Define the Client model
class Client(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Name must be between 1 and 100 characters
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Address must be between 1 and 255 characters
    phone_number: Annotated[str, StringConstraints(pattern=r"^\+?\d{10,15}$")]  # Phone number must be 10-15 digits, optional "+" at the start
    email: EmailStr  # Valid email format
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{15}$")] | None = None  # Optional NPWP, must be 15 digits
    uuid: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")] | None = None  # Optional UUID, must be in valid format
    
# Define the clients table
clients_table = Table(
    "clients",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("phone_number", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(50), nullable=True),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime(), nullable=False,default=date.today()),
    Column("created_by", Integer, nullable=False),
    Column("updated_at", DateTime(), nullable=True,default=None),
    Column("updated_by", Integer, nullable=True, default=None),
    Column("is_delete", Boolean, default=False),
    Column("deleted_at", DateTime(), nullable=True, default=None),
    Column("deleted_by", Integer, nullable=True, default=None),
    Column("uuid", String(50), nullable=False, unique=True),
)