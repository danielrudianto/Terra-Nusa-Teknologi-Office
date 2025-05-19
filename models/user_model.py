#Create a user
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, ForeignKey
from utils.database import metadata
from datetime import datetime

# Define the User model
class User(BaseModel):
    id: int  # Unique ID for the user
    password: str  # Password of the user
    name: str # Name of the user
    email: str  # Email address of the user
    isActive: bool = True  # Flag to indicate if the user is active
    isDeleted: bool = False  # Flag to indicate if the user is deleted
    createdBy: Optional[int] = None  # ID of the user who created this user (optional)
    createdAt: datetime  # Date when the user was created
    updated_at: Optional[datetime] = None  # Date when the user was last updated (optional)
    deleted_at: Optional[datetime] = None  # Date when the user was deleted (optional)
    
# Define the SQLAlchemy table
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("password", String(255)),
    Column("email", String(100), unique=True),
    Column("isActive", Boolean, default=True),
    Column("isDeleted", Boolean, default=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=datetime.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None)
)