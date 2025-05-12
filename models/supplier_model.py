from pydantic import BaseModel, EmailStr, StringConstraints
from typing import Annotated
from sqlalchemy import ForeignKey, Table, Column, Integer, String, Boolean
from utils.database import metadata

# Define the Client model
class Supplier(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Name must be between 1 and 100 characters
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Address must be between 1 and 255 characters
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # City must be between 1 and 100 characters
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Province must be between 1 and 100 characters
    phone_number: Annotated[str, StringConstraints(pattern=r"^\+?\d{7,20}$")]  # Phone number must be 10-15 digits, optional "+" at the start
    email: Annotated[EmailStr, StringConstraints(max_length=255)] | None = None  #Nullable string, must be a valid email format
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None  # Optional NPWP, must be 16 digits
    items_sold: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Items sold must be between 1 and 255 characters
    service_area: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Service area must be between 1 and 255 characters
    is_active: bool = True  # Default to True


# Define the clients table
suppliers_table = Table(
    "suppliers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(100), nullable=False),
    Column("province", String(100), nullable=False),
    Column("phone_number", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(16), nullable=True),
    Column("is_active", Boolean, default=True),
    Column("items_sold", String(1000), nullable=False),
    Column("service_area", String(1000), nullable=False),
    Column("created_at", String(50), nullable=False),
    Column("created_by", Integer, ForeignKey("users.id"), nullable=False),
)