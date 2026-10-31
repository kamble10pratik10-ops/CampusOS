"""
Backend authorization helpers.

Role definitions
----------------
principal   : Institution-wide read access to all supported operations.
hod         : Access restricted to the faculty member's own department.
              Cross-department requests must be rejected with HTTP 403.
exam_cell   : Access to examination endpoints (deferred — returns 501 until M-exam).

IMPORTANT: Role enforcement happens HERE on the backend.
Frontend role display is informational only and must never substitute for this check.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import RoleEnum, User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Decode the bearer token, look up the user in the database, and return
    the ORM object.  Raises HTTP 401 on any failure — never trusts payload
    claims without verifying against the DB.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exc
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


# ── Dependency shortcuts ──────────────────────────────────────────────────

CurrentUser = Annotated[User, Depends(_get_current_user)]


def require_principal(current_user: CurrentUser) -> User:
    """Dependency: allow only the principal role."""
    if current_user.role != RoleEnum.principal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Principal role required",
        )
    return current_user


def require_hod_or_principal(current_user: CurrentUser) -> User:
    """Dependency: allow HOD or Principal."""
    if current_user.role not in (RoleEnum.principal, RoleEnum.hod):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD or Principal role required",
        )
    return current_user


def check_department_access(user: User, target_department_id: uuid.UUID) -> None:
    """
    Raise HTTP 403 if an HOD tries to access a different department's data.
    Principal has unrestricted access.
    """
    if user.role == RoleEnum.principal:
        return  # Full access
    if user.role == RoleEnum.hod:
        if user.department_id != target_department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"HOD access is restricted to department {user.department_id}. "
                    f"Requested department {target_department_id} is not permitted."
                ),
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions for this operation",
    )
