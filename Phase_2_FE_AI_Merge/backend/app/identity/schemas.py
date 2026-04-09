from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    displayName: Optional[str] = None
    role: str = "student"
    photoURL: Optional[str] = None
    persona: Optional[str] = None
    educationDescription: Optional[str] = None


class UserCreate(UserBase):
    uid: str
    authProvider: Optional[str] = None
    passwordHash: Optional[str] = None


class UserUpdate(BaseModel):
    displayName: Optional[str] = None
    role: Optional[str] = None
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
    displayName: Optional[str] = None


class LocalLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthSessionResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    auth_provider: str
