"""Security primitives: password hashing (bcrypt) and JWT tokens (PyJWT).

Library choices (industry-standard, actively maintained):
- ``bcrypt`` (pyca team) — modern password hashing. The plan named
  ``passlib[bcrypt]`` but passlib is effectively unmaintained since 2020 and
  is incompatible with recent ``bcrypt`` releases and Python 3.13+.
- ``PyJWT`` — the de-facto standard JWT library. ``python-jose`` (named in
  the plan) has known CVEs and is no longer recommended by the FastAPI docs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=get_settings().BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain-text password against a bcrypt hash (constant-time)."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    role: str,
    token_version: int | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token.

    ``token_version`` carries the user's current ``token_version`` so that
    single-session enforcement can reject tokens minted before a new login
    (or before logout). Admins are exempt and pass ``None``.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(
            minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }
    if token_version is not None:
        payload["ver"] = token_version
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` for invalid tokens."""
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])