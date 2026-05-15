"""Pydantic request & response DTOs for users."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from superticket.models.enums import UserRole


class UserCreate(BaseModel):
    """Fields required to register a new user."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: UserRole = UserRole.USER


class UserOut(BaseModel):
    """Read-only user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
