"""Audit log for manual reward adjustments by admins."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RewardAdjustment(Base):
    """Every manual reward-counter change is persisted here for accountability."""

    __tablename__ = "reward_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship()  # noqa: F821
    admin: Mapped["Admin"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RewardAdjustment id={self.id} user={self.user_id} delta={self.delta}>"