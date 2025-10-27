from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Pydantic schemas for request/response
class UserBase(BaseModel):
    name: str
    email: str
    authenticationLevel: Optional[int] = Field(default=1, ge=1, le=5, description="Authentication level of the user, between 1 and 5")

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    id: int
    isActive: bool
    isDeleted: bool
    createdBy: Optional[int] = None
    createdAt: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    message: str
    user_id: int
    email: str
    name: str
    authenticationLevel: int

class ErrorResponse(BaseModel):
    error: str
    status: int