"""
Authentication API routes.

POST /auth/token  — OAuth2 password flow, returns JWT
GET  /auth/me     — returns current authenticated user

SECURITY NOTE: This is a demo-only implementation.
No token revocation, no refresh tokens, no rate limiting on login attempts.
Do not use in production without addressing these limitations.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import CurrentUser
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login and obtain an access token",
    description=(
        "OAuth2 password flow. Submit email as 'username' and password. "
        "Returns a JWT bearer token valid for 8 hours. "
        "**DEMO ONLY**: no rate limiting or token revocation is implemented."
    ),
)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    # Look up user by email (form_data.username = email in our scheme)
    user: User | None = (
        db.query(User).filter(User.email == form_data.username).first()
    )
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "dept": str(user.department_id)},
        expires_delta=expires,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires.total_seconds()),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current authenticated user",
)
def get_me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)
