"""Transaction routes: invoice submission (with daily-limit enforcement)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.transaction import InvoiceSubmitRequest, TransactionCreatedOut
from app.services import transactions as tx_service
from app.services.notifications import bus

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionCreatedOut, status_code=201)
async def submit_invoice(payload: InvoiceSubmitRequest, user: CurrentUser, db: DbSession):
    """Submit a physical-store invoice number to earn a reward.

    Enforces the daily usage limit (3 uses per business per calendar day,
    independent per business) and rejects duplicate invoice numbers.
    """
    settings = get_settings()
    transaction = tx_service.submit_invoice(
        db,
        user=user,
        business_id=payload.business_id,
        invoice_number=payload.invoice_number,
    )

    used_today = tx_service.count_uses_today(db, user.id, transaction.business_id)
    remaining = max(0, settings.DAILY_LIMIT_PER_BUSINESS - used_today)

    # Push a real-time purchase alert to connected admin dashboards.
    await bus.publish(
        "purchase",
        {
            "transaction_id": transaction.id,
            "user_id": user.id,
            "user_name": user.name,
            "business_id": transaction.business_id,
            "business_name": transaction.business.name if transaction.business else None,
            "invoice_number": transaction.invoice_number,
            "reward_increment": transaction.reward_increment,
            "created_at": transaction.created_at,
        },
    )

    return TransactionCreatedOut(
        id=transaction.id,
        business_id=transaction.business_id,
        business_name=transaction.business.name if transaction.business else None,
        invoice_number=transaction.invoice_number,
        reward_increment=transaction.reward_increment,
        created_at=transaction.created_at,
        used_today=used_today,
        remaining_today=remaining,
        reward_points_balance=user.reward_points,
    )