"""Transaction model — a verified invoice submission that increments rewards.

The daily usage limit (3 uses per business per calendar day) is *derived* from
this table by counting rows for a given (user, business) created after the
start of the current calendar day. This makes the limit automatically "reset"
at midnight with no background job required.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # Prevent submitting the same invoice twice for the same business.
        UniqueConstraint(
            "user_id", "business_id", "invoice_number",
            name="uq_user_business_invoice",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    reward_increment: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, index=True, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="transactions")  # noqa: F821
    business: Mapped["Business"] = relationship(back_populates="transactions")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Transaction id={self.id} user={self.user_id} "
            f"business={self.business_id} invoice={self.invoice_number!r}>"
        )