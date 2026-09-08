"""Authentication and account-lifecycle service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    EmailConflictError,
    InvalidCredentialsError,
    MembershipExpiredError,
    UserInactiveError,
    UserNotFoundError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Admin, User

try:
    from email_validator import validate_email as validate_email_address

    def _is_email(value: str) -> bool:
        try:
            return bool(validate_email_address(value, check_deliverability=False).normalized)
        except Exception:
            return False
except ImportError:  # pragma: no cover
    def _is_email(value: str) -> bool:
        return "@" in value and "." in value.split("@")[-1]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def authenticate_and_login_user(db: Session, identifier: str, password: str) -> User:
    """Lookup by email or CPR, verify password, enforce status & expiry, then
    bump token_version (single-session) and issue a fresh token.

    Returns the authenticated ``User``; raises AppErrors otherwise.
    """
    settings = get_settings()

    # --- lookup by email or CPR -------------------------------------------
    if _is_email(identifier):
        user = db.scalar(select(User).where(User.email == identifier.lower()))
    else:
        user = db.scalar(select(User).where(User.cpr == identifier))

    if user is None:
        raise InvalidCredentialsError

    # --- password ---------------------------------------------------------
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    # --- status guards -----------------------------------------------------
    if not user.is_active:
        raise UserInactiveError

    if user.expiry_date is not None and user.expiry_date <= _now():
        raise MembershipExpiredError(
            "Your membership has expired. Please contact the organization to renew."
        )

    # --- single-session enforcement ----------------------------------------
    user.token_version += 1
    db.add(user)
    db.commit()
    return user


def issue_user_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        role="user",
        token_version=user.token_version,
        expires_minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def login_admin(db: Session, username: str, password: str) -> Admin:
    """Authenticate an admin. Admins are exempt from single-session rules."""
    admin = db.scalar(select(Admin).where(Admin.username == username))
    if admin is None or not verify_password(password, admin.password_hash):
        raise InvalidCredentialsError
    return admin


def issue_admin_token(admin: Admin) -> str:
    return create_access_token(
        subject=str(admin.id),
        role="admin",
        token_version=None,
        expires_minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def activate_profile(db: Session, user: User, name: str, email: str, new_password: str) -> User:
    """First-login profile activation: update identity details and set a new
    password, then clear the ``must_change_password`` flag."""
    candidate = db.scalar(select(User).where(User.email == email.lower()))
    if candidate is not None and candidate.id != user.id:
        raise EmailConflictError

    user.name = name
    user.email = email.lower()
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError
    user.password_hash = hash_password(new_password)
    # Invalidate sessions from other devices — keep only this one.
    user.token_version += 1
    db.add(user)
    db.commit()


def force_logout(db: Session, user: User) -> None:
    """Invalidate all existing sessions for a user (single-session)."""
    user.token_version += 1
    db.add(user)
    db.commit()


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user