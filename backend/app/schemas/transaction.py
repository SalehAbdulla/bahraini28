"""Transaction schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class InvoiceSubmitRequest(BaseModel):
    business_id: int = Field(gt=0)
    invoice_number: str = Field(min_length=3, max_length=64)


class TransactionOut(ORMModel):
    id: int
    business_id: int
    business_name: str
    invoice_number: str
    reward_increment: int
    created_at: datetime


class TransactionCreatedOut(TransactionOut):
    """Response for a successful invoice submission."""

    used_today: int
    remaining_today: int
    reward_points_balance: int