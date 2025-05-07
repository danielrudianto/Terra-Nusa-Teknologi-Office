from pydantic import BaseModel, EmailStr, StringConstraints
from typing import Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean
from utils.database import metadata

# Define the Client model
class Supplier(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Name must be between 1 and 100 characters
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Address must be between 1 and 255 characters
    phone_number: Annotated[str, StringConstraints(pattern=r"^\+?\d{10,15}$")]  # Phone number must be 10-15 digits, optional "+" at the start
    email: EmailStr  # Valid email format
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None  # Optional NPWP, must be 16 digits

# Define the clients table
suppliers_table = Table(
    "suppliers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("phone_number", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(16), nullable=True),
    Column("is_active", Boolean, default=True),
)