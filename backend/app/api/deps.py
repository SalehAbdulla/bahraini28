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
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
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


def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> User | None:
    """Resolve the caller when they present a *valid* user token, else ``None``.

    This is the public-directory variant of :func:`get_current_user`: an
    anonymous visitor (no token) is never rejected - they simply receive the
    redacted view (e.g. no discount figures). A malformed, expired, revoked or
    expired-membership token is treated as anonymous too, so a stale token in a
    browser can never break a public page with a 401.

    The membership guards deliberately mirror :func:`get_current_user`, so the
    member-only reveal uses exactly the same definition of "valid member".
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        return None
    if payload.get("role") != "user":
        return None

    try:
        user = db.get(User, int(payload["sub"]))
    except (KeyError, TypeError, ValueError):
        return None
    if user is None:
        return None

    # --- single-session enforcement ---------------------------------------
    if payload.get("ver") != user.token_version:
        return None

    # --- status guards ------------------------------------------------------
    if not user.is_active:
        return None
    if user.expiry_date is not None and user.expiry_date <= datetime.now(timezone.utc):
        return None

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
#: Like ``CurrentUser`` but ``None`` for an anonymous (or invalid-token) caller.
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]


def get_app_settings(request: Request) -> Settings:
    """Return the settings the running app was created with.

    Reads ``app.state.settings`` (set in ``create_app``) rather than the cached
    global so tests / embedded apps that inject custom settings see the same
    ``UPLOAD_DIR``/limits the app was mounted with.
    """
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_app_settings)]