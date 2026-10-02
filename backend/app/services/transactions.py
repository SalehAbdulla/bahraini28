"""Transaction service — invoice submission with anti-fraud gates.

Layered defence (Tier 1):

1. **Format gate** — the invoice must match the partner's ``invoice_pattern``
   (or the global fallback). Rejects junk like ``"1"`` or ``"!!!"``.
2. **Global duplicate guard** — an invoice can be credited only once per
   business, *by anyone*, so a receipt cannot be shared between accounts.
3. **Per-business daily limit** — ``DAILY_LIMIT_PER_BUSINESS`` uses today.
4. **Total daily limit** — ``DAILY_LIMIT_TOTAL`` across every partner, so a
   single account cannot farm 3 x N fabricated invoices across the directory.

The daily counters are *derived* from the ``transactions`` table (rows created
on or after the start of the current calendar day in the configured timezone),
so they reset at midnight with no cron/background task.

None of this proves a purchase happened; real verification (receipt proof +
admin approval) is the planned Tier 2 milestone.
"""
from __future__ import annotations

import re
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
    InvoiceFormatError,
    TotalDailyLimitExceededError,
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


def count_uses_today_total(db: Session, user_id: int) -> int:
    """All successful submissions by ``user_id`` today, across every partner."""
    start = start_of_calendar_day()
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= start,
    )
    return int(db.scalar(stmt) or 0)


def count_distinct_businesses_today(db: Session, user_id: int) -> int:
    """How many *different* partners ``user_id`` has credited today.

    Used to raise an admin fraud signal when a single account sprays invoices
    across many businesses in one day.
    """
    start = start_of_calendar_day()
    stmt = select(func.count(func.distinct(Transaction.business_id))).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= start,
    )
    return int(db.scalar(stmt) or 0)


def normalize_invoice_number(value: str) -> str:
    """Canonical form used for storage and uniqueness (trim + upper)."""
    return value.strip().upper()


def validate_invoice_format(business: Business, invoice_number: str) -> None:
    """Reject invoice numbers that cannot plausibly be a real receipt.

    Uses the partner's own ``invoice_pattern`` when set, otherwise the global
    fallback. A malformed admin pattern degrades to the fallback rather than
    locking the partner out.
    """
    settings = get_settings()
    try:
        compiled = re.compile(business.invoice_pattern, re.IGNORECASE)
    except (re.error, TypeError):
        compiled = re.compile(settings.INVOICE_DEFAULT_PATTERN, re.IGNORECASE)
    if compiled.fullmatch(invoice_number) is None:
        raise InvoiceFormatError


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
    """Create a transaction for a verified invoice, enforcing every gate.

    Raises ``InvoiceFormatError`` (400) for implausible invoice numbers,
    ``DuplicateInvoiceError`` (409) for an invoice already credited at this
    partner, ``DailyLimitExceededError`` (429) once this business is used
    ``DAILY_LIMIT_PER_BUSINESS`` times today, and ``TotalDailyLimitExceededError``
    (429) once the all-partners ceiling is reached.
    """
    settings = get_settings()
    business = get_usable_business(db, business_id)
    invoice = normalize_invoice_number(invoice_number)

    # --- 1. format gate ------------------------------------------------------
    validate_invoice_format(business, invoice)

    # --- 2. global duplicate guard (any user, this business) -----------------
    existing = db.scalar(
        select(Transaction.id).where(
            Transaction.business_id == business.id,
            Transaction.invoice_number == invoice,
        )
    )
    if existing is not None:
        raise DuplicateInvoiceError(
            "This invoice number has already been credited at this partner."
        )

    # --- 3. per-business daily limit ----------------------------------------
    used_today = count_uses_today(db, user.id, business.id)
    if used_today >= settings.DAILY_LIMIT_PER_BUSINESS:
        raise DailyLimitExceededError

    # --- 4. total daily limit across all partners ---------------------------
    if count_uses_today_total(db, user.id) >= settings.DAILY_LIMIT_TOTAL:
        raise TotalDailyLimitExceededError

    # --- create -------------------------------------------------------------
    transaction = Transaction(
        user_id=user.id,
        business_id=business.id,
        invoice_number=invoice,
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