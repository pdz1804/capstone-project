from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    displayName: Optional[str] = None
    role: str = "student"
    isActive: bool = True
    photoURL: Optional[str] = None
    persona: Optional[str] = None
    educationDescription: Optional[str] = None


class UserCreate(UserBase):
    uid: str
    authProvider: Optional[str] = None
    passwordHash: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    displayName: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None
    photoURL: Optional[str] = None
    persona: Optional[str] = None
    educationDescription: Optional[str] = None
    lastLogin: Optional[datetime] = None


class UserResponse(UserBase):
    uid: str
    authProvider: Optional[str] = None
    createdAt: datetime
    lastLogin: Optional[datetime] = None

    class Config:
        from_attributes = True


class LocalRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None
    displayName: Optional[str] = None
    role: str = "student"


class LocalLoginRequest(BaseModel):
    email: str
    password: str


class AuthSessionResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    auth_provider: str
