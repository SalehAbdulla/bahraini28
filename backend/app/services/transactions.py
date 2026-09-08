"""Transaction service — invoice submission with daily-usage-limit checks.

The daily limit ("3 uses per business per calendar day") is enforced by
counting rows in the ``transactions`` table whose ``created_at`` is on or
after the start of the current calendar day (computed in the configured
timezone). Because the count window derives from the wall-clock date, the
limit is automatically reset at midnight with no cron/background task.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    BusinessExpiredError,
    BusinessInactiveError,
    BusinessNotFoundError,
    DailyLimitExceededError,
    DuplicateInvoiceError,
)
from app.models import Business, Transaction, User


def start_of_calendar_day(tz_name: str | None = None, reference: datetime | None = None) -> datetime:
    """Return the UTC instant that starts the current calendar day in ``tz``.

    ``reference`` is an injectable clock for tests.
    """
    tz = ZoneInfo(tz_name or get_settings().DEFAULT_TIMEZONE)
    now_local = (reference or datetime.now(timezone.utc)).astimezone(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc)


def count_uses_today(db: Session, user_id: int, business_id: int) -> int:
    """Number of successful uses by ``user_id`` at ``business_id`` today."""
    start = start_of_calendar_day()
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.business_id == business_id,
        Transaction.created_at >= start,
    )
    return int(db.scalar(stmt) or 0)


def get_usable_business(db: Session, business_id: int) -> Business:
    """Fetch a business, guarding against missing/inactive/expired records."""
    business = db.get(Business, business_id)
    if business is None:
        raise BusinessNotFoundError
    if not business.is_active:
        raise BusinessInactiveError
    if business.expiry_date is not None and business.expiry_date <= datetime.now(timezone.utc):
        raise BusinessExpiredError
    return business


def submit_invoice(
    db: Session,
    *,
    user: User,
    business_id: int,
    invoice_number: str,
) -> Transaction:
    """Create a transaction for a verified invoice, enforcing the daily limit.

    Raises ``DuplicateInvoiceError`` (409) for repeat submissions and
    ``DailyLimitExceededError`` (429) once the user hits the 3-use ceiling at
    this business today.
    """
    settings = get_settings()
    business = get_usable_business(db, business_id)

    # --- duplicate submission guard ---------------------------------------
    existing = db.scalar(
        select(Transaction.id).where(
            Transaction.user_id == user.id,
            Transaction.business_id == business.id,
            Transaction.invoice_number == invoice_number.strip(),
        )
    )
    if existing is not None:
        raise DuplicateInvoiceError

    # --- daily usage limit ------------------------------------------------
    used_today = count_uses_today(db, user.id, business.id)
    if used_today >= settings.DAILY_LIMIT_PER_BUSINESS:
        raise DailyLimitExceededError

    # --- create -------------------------------------------------------------
    transaction = Transaction(
        user_id=user.id,
        business_id=business.id,
        invoice_number=invoice_number.strip(),
        reward_increment=1,
    )
    db.add(transaction)
    user.reward_points += transaction.reward_increment
    db.commit()
    db.refresh(transaction)
    return transaction


def paginate_transactions(
    db: Session,
    *,
    user_id: int | None = None,
    business_id: int | None = None,
    page: int = 1,
    page_size: int = 12,
) -> tuple[list[Transaction], int]:
    """Paginated transaction history with descending creation order."""
    stmt = select(Transaction)
    count_stmt = select(func.count(Transaction.id))
    if user_id is not None:
        stmt = stmt.where(Transaction.user_id == user_id)
        count_stmt = count_stmt.where(Transaction.user_id == user_id)
    if business_id is not None:
        stmt = stmt.where(Transaction.business_id == business_id)
        count_stmt = count_stmt.where(Transaction.business_id == business_id)

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            stmt.order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total