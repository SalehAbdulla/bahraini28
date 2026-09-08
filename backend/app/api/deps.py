"""FastAPI dependencies: bearer-token auth for users and admins.

Security decisions baked into these dependencies:
- **Users**: role must be ``user``, the token's ``ver`` claim must equal the
  user's current ``token_version`` (single-session enforcement), the account
  must be active, and the membership expiry date must not have passed.
- **Admins**: role must be ``admin``; admins are exempt from the
  single-session check per the product specification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import (
    InvalidTokenError,
    MembershipExpiredError,
    NotAuthenticatedError,
    SessionInvalidatedError,
    UserInactiveError,
    UserNotFoundError,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.models import Admin, User

bearer_scheme: HTTPBearer = HTTPBearer(auto_error=False)


def _extract_credentials(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise NotAuthenticatedError
    try:
        return decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired. Please log in again.") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError from exc


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> User:
    payload = _extract_credentials(credentials)
    if payload.get("role") != "user":
        raise InvalidTokenError("Token is not a user token.")

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise UserNotFoundError

    # --- single-session enforcement ---------------------------------------
    if payload.get("ver") != user.token_version:
        raise SessionInvalidatedError

    # --- status guards ------------------------------------------------------
    if not user.is_active:
        raise UserInactiveError
    if user.expiry_date is not None and user.expiry_date <= datetime.now(timezone.utc):
        raise MembershipExpiredError

    return user


def get_current_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> Admin:
    payload = _extract_credentials(credentials)
    if payload.get("role") != "admin":
        raise InvalidTokenError("Token is not an admin token.")

    admin = db.get(Admin, int(payload["sub"]))
    if admin is None:
        raise InvalidTokenError("Admin account no longer exists.")
    return admin


# --- convenience type aliases -------------------------------------------------
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]