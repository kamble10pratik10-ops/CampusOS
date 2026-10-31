"""Pydantic schemas for authentication."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.db.models import RoleEnum


class TokenRequest(BaseModel):
    """OAuth2 password flow request (form data)."""
    # Handled by FastAPI's OAuth2PasswordRequestForm dependency


class TokenResponse(BaseModel):
    """Successful login response."""
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserPublic(BaseModel):
    """Safe user representation — never includes hashed_password."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    role: RoleEnum
    department_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class LoginError(BaseModel):
    detail: str
