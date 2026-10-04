"""Merchant one-time invoice codes (anti-fraud Tier 3).

An admin issues a *batch* of codes to one partner; every code is single-use and
bound to that partner. The volunteer quotes the code printed on their receipt, so
a fabricated number can never match an unused code — the one control that makes
invoicing *provable* rather than merely plausible.

Lifecycle::

    issued --(submitted)--> claimed --(approved)--> redeemed
      ^                        |
      +----(rejected)----------+

* ``claimed`` reserves the code while the submission sits in the review queue,
  so the same code cannot back two submissions at once.
* ``redeemed`` is terminal — a code that earned a reward can never be reused.
* A **rejected** submission releases its code back to ``issued``: an honest
  mistake (a blurry photo) must not burn the volunteer's only code.
* ``revoked`` lets an admin cancel a code that was never handed out.

A code is never deleted, only moved between these states, so the printed sheet
an admin handed to a partner can always be reconciled after the fact.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime

#: Code lifecycle values. Plain strings (matching the rest of the project, which
#: uses no SQL ``Enum`` type), constrained by the application.
CODE_ISSUED = "issued"
CODE_CLAIMED = "claimed"
CODE_REDEEMED = "redeemed"
CODE_REVOKED = "revoked"
#: Every value, for validation and reporting.
CODE_STATUSES = (CODE_ISSUED, CODE_CLAIMED, CODE_REDEEMED, CODE_REVOKED)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceCode(Base):
    """A single-use code printed on a partner's receipt."""

    __tablename__ = "invoice_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: The code itself (``B28-XXXX-XXXX``). Globally unique, so a code issued to
    #: one partner can never be quoted at another.
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=CODE_ISSUED, index=True, nullable=False
    )
    #: Optional admin label, so a printed sheet can be traced back to a batch.
    batch: Mapped[str | None] = mapped_column(String(60), nullable=True)
    #: Admin who generated the code (kept nullable so the row survives an admin
    #: being removed — the audit value is the timestamp, not the link).
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, index=True, nullable=False
    )
    #: Set while a submission holds the code (cleared again on rejection).
    claimed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="invoice_codes")  # noqa: F821
    claimed_by_user: Mapped["User | None"] = relationship()  # noqa: F821

    @property
    def is_available(self) -> bool:
        """True while the code can still be claimed by a submission."""
        return self.status == CODE_ISSUED

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<InvoiceCode id={self.id} business={self.business_id} "
            f"code={self.code!r} status={self.status}>"
        )
