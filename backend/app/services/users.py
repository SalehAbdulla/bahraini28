"""User account service (profile management)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import EmailConflictError, UserNotFoundError
from app.models import Transaction, User


def get_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user


def update_me(db: Session, user: User, name: str | None, email: str | None, phone: str | None) -> User:
    if email is not None:
        candidate = db.scalar(select(User).where(User.email == email.lower()))
        if candidate is not None and candidate.id != user.id:
            raise EmailConflictError
        user.email = email.lower()
    if name is not None:
        user.name = name
    if phone is not None:
        user.phone = phone.strip() or None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def profile_computed(user: User) -> dict:
    """Computed membership/rewards metadata attached to API responses."""
    now = datetime.now(timezone.utc)
    is_expiring_soon = 0 <= (user.expiry_date - now).total_seconds() <= 30 * 24 * 3600
    return {
        "membership_status": "active" if user.is_active and user.expiry_date > now else (
            "expired" if user.expiry_date <= now else "inactive"
        ),
        "expiry_soon": is_expiring_soon,
    }