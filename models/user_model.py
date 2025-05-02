#Create a user
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime
from utils.database import metadata
from datetime import datetime

# Define the User model
class User(BaseModel):
    id: int  # Unique ID for the user
    password: str  # Password of the user
    name: str # Name of the user
    email: str  # Email address of the user
    is_active: bool = True  # Flag to indicate if the user is active
    is_deleted: bool = False  # Flag to indicate if the user is deleted
    created_at: datetime  # Date when the user was created
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
    Column("is_active", Boolean, default=True),
    Column("is_deleted", Boolean, default=False),
    Column("created_at", DateTime(), nullable=False, default=datetime.now()),
    Column("updated_at", DateTime(), nullable=True, default=None),
    Column("deleted_at", DateTime(), nullable=True, default=None)
)