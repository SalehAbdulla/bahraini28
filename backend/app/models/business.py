"""Merchant partner (Business) model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    # Commercial Registration number.
    commercial_registration: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    # Logo stored as a static file path (optional).
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Partnership validity — bookings stop after this date.
    expiry_date: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    category: Mapped["Category"] = relationship(back_populates="businesses")  # noqa: F821
    areas: Mapped[list["BusinessArea"]] = relationship(  # noqa: F821
        back_populates="business", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="business", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Business id={self.id} name={self.name!r}>"