"""Volunteer user model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cpr: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Membership validity — access is blocked after this date.
    expiry_date: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Forces the first-login "profile activation" flow.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Accumulated rewards from invoice submissions (and manual adjustments).
    reward_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Single-session enforcement: every new login/logout bumps this version and
    # mints a token carrying it; older tokens become invalid.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} cpr={self.cpr!r} name={self.name!r}>"