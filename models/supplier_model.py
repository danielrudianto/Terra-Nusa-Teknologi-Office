from pydantic import BaseModel, EmailStr, StringConstraints
from typing import Annotated
from sqlalchemy import ForeignKey, Table, Column, Integer, String, Boolean
from utils.database import metadata

# Define the Client model
class Supplier(BaseModel):
    prefix: Annotated[str, StringConstraints(min_length=1, max_length=25)] | None = None  # Optional prefix, max length 25
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Name must be between 1 and 100 characters
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Address must be between 1 and 255 characters
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # City must be between 1 and 100 characters
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Province must be between 1 and 100 characters
    phoneNumber: Annotated[str, StringConstraints(pattern=r"^\+?\d{7,20}$")]  # Phone number must be 10-15 digits, optional "+" at the start
    email: Annotated[EmailStr, StringConstraints(max_length=255)] | None = None  #Nullable string, must be a valid email format
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None  # Optional NPWP, must be 16 digits
    itemsSold: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Items sold must be between 1 and 255 characters
    serviceArea: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Service area must be between 1 and 255 characters
    isActive: bool = True  # Default to True


# Define the clients table
suppliers_table = Table(
    "suppliers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("prefix" , String(25), nullable=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(100), nullable=False),
    Column("province", String(100), nullable=False),
    Column("phoneNumber", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(16), nullable=True),
    Column("itemsSold", String(1000), nullable=False),
    Column("serviceArea", String(1000), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", String(50), nullable=False),
    Column("isActive", Boolean, default=True),
)