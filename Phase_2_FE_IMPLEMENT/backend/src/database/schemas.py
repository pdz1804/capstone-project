from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    displayName: Optional[str] = None
    role: str = "student"
    photoURL: Optional[str] = None

class UserCreate(UserBase):
    uid: str

class UserUpdate(BaseModel):
    displayName: Optional[str] = None
    role: Optional[str] = None
    photoURL: Optional[str] = None
    lastLogin: Optional[datetime] = None

class UserResponse(UserBase):
    uid: str
    createdAt: datetime
    lastLogin: Optional[datetime] = None

    class Config:
        from_attributes = True
