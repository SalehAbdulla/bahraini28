"""Transaction schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class InvoiceSubmitRequest(BaseModel):
    """JSON form of the submission.

    Kept for the Tier-1 fallback (``REQUIRE_RECEIPT_REVIEW=False``) and for
    deployments whose frontend has not been updated to the multipart flow yet;
    the multipart path needs no receipt *file* in that mode either.
    """

    business_id: int = Field(gt=0)
    invoice_number: str = Field(min_length=3, max_length=64)


class TransactionOut(ORMModel):
    id: int
    business_id: int
    business_name: str
    invoice_number: str
    reward_increment: int
    created_at: datetime
    #: ``pending`` | ``approved`` | ``rejected`` (see ``models.transaction``).
    status: str
    #: Only ever populated on the volunteer's *own* history — never on the
    #: public per-business list, so a rejection note stays private.
    rejection_reason: str | None = None


class TransactionCreatedOut(TransactionOut):
    """Response for a successful invoice submission."""

    used_today: int
    remaining_today: int
    used_today_total: int
    remaining_today_total: int
    reward_points_balance: int


class TransactionReviewOut(TransactionOut):
    """Admin review-queue view: adds the volunteer and the receipt evidence."""

    user_id: int
    user_name: str
    receipt_url: str | None = None
    reviewed_at: datetime | None = None


class RejectTransactionRequest(BaseModel):
    """Admin rejection. The reason is stored and shown to the volunteer."""

    reason: str | None = Field(None, min_length=2, max_length=255)