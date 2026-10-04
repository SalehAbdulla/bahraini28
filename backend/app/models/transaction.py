"""Transaction model — an invoice submission that earns a reward after review.

Two rules live here:

* **Tier 1 (anti-fraud):** an invoice number can only ever be credited once per
  business — *by anyone* — so a receipt cannot be shared across accounts.
* **Tier 2 (proof):** a submission carries the receipt evidence and moves
  ``pending → approved | rejected``. ``reward_points`` is only credited on
  approval, so ``status`` is what decides whether a row is spendable.

The daily usage limit is *derived* from this table by counting rows for a given
(user, business) created after the start of the current calendar day, so the
limit "resets" at midnight with no background job required.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime

# Review lifecycle values. Plain strings (matching the rest of the project,
# which uses no SQL ``Enum`` type), constrained by the application.
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
#: Statuses that still occupy a daily-cap slot — a queued submission must not
#: bypass the caps by sitting unreviewed, while a *rejected* one must not
#: punish a volunteer for an honest mistake.
COUNTED_STATUSES = (STATUS_PENDING, STATUS_APPROVED)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # An invoice may only ever be credited ONCE per business — by anyone.
        # Scoping this to (user_id, business_id, invoice) was the fraud hole:
        # a receipt could be shared across accounts, and fabricated numbers
        # were accepted outright.
        UniqueConstraint(
            "business_id", "invoice_number",
            name="uq_business_invoice",
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

    # --- Tier 2: receipt proof + admin review --------------------------------
    # ``status`` is always set explicitly by the service; the server default is
    # the safe one (nothing is spendable until a human has looked at it).
    status: Mapped[str] = mapped_column(
        String(16), default=STATUS_PENDING, index=True, nullable=False
    )
    #: Public URL of the uploaded receipt (``/uploads/r<business>-<uuid>.jpg``).
    receipt_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: SHA-256 of the receipt bytes — a second receipt image for the same
    #: partner is rejected, so one photo cannot be recycled for many credits.
    receipt_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Tier 3: single-use merchant receipt code ----------------------------
    #: The one-time code this submission spent (``None`` when the partner does
    #: not require codes). Kept ``SET NULL`` so the transaction — and the reward
    #: it earned — survives the code row being cleaned up.
    code_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice_codes.id", ondelete="SET NULL"), index=True, nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="transactions")  # noqa: F821
    business: Mapped["Business"] = relationship(back_populates="transactions")  # noqa: F821
    code: Mapped["InvoiceCode | None"] = relationship()  # noqa: F821

    @property
    def is_pending(self) -> bool:
        return self.status == STATUS_PENDING

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Transaction id={self.id} user={self.user_id} "
            f"business={self.business_id} invoice={self.invoice_number!r} "
            f"status={self.status}>"
        )