"""Transaction service — invoice submission, anti-fraud gates and review.

Layered defence (Tier 1):

1. **Format gate** — the invoice must match the partner's ``invoice_pattern``
   (or the global fallback). Rejects junk like ``"1"`` or ``"!!!"``.
2. **Global duplicate guard** — an invoice can be credited only once per
   business, *by anyone*, so a receipt cannot be shared between accounts.
3. **Per-business daily limit** — ``DAILY_LIMIT_PER_BUSINESS`` uses today.
4. **Total daily limit** — ``DAILY_LIMIT_TOTAL`` across every partner, so a
   single account cannot farm 3 x N fabricated invoices across the directory.

Tier 2 adds *proof* on top of that hardening:

5. **Receipt evidence** — the volunteer uploads a receipt image/PDF; its
   SHA-256 is stored so the *same photo* cannot credit two invoices at the same
   partner.
6. **Admin approval** — a submission is created as ``pending`` and **does not
   touch ``reward_points``**. Only :func:`approve_transaction` credits a reward
   (and writes a :class:`~app.models.reward_adjustment.RewardAdjustment` audit
   row); :func:`reject_transaction` leaves the counter alone. The single
   exception is the documented Tier-1 fallback
   (``REQUIRE_RECEIPT_REVIEW=False``), which keeps the old instant-credit
   behaviour so an un-onboarded deployment still works.

The daily counters are *derived* from the ``transactions`` table (rows created
on or after the start of the current calendar day in the configured timezone),
so they reset at midnight with no cron/background task. ``pending`` rows **do**
consume a daily slot (queueing must not bypass the cap) while ``rejected`` rows
do not (an honest mistake should not cost a volunteer their quota).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import (
    BusinessExpiredError,
    BusinessInactiveError,
    BusinessNotFoundError,
    DailyLimitExceededError,
    DuplicateInvoiceError,
    InvoiceFormatError,
    TotalDailyLimitExceededError,
    TransactionNotFoundError,
    TransactionNotPendingError,
)
from app.models import Admin, Business, RewardAdjustment, Transaction, User
from app.models.transaction import (
    COUNTED_STATUSES,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)


def start_of_calendar_day(tz_name: str | None = None, reference: datetime | None = None) -> datetime:
    """Return the UTC instant that starts the current calendar day in ``tz``.

    ``reference`` is an injectable clock for tests.
    """
    tz = ZoneInfo(tz_name or get_settings().DEFAULT_TIMEZONE)
    now_local = (reference or datetime.now(timezone.utc)).astimezone(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc)


def count_uses_today(db: Session, user_id: int, business_id: int) -> int:
    """Number of successful uses by ``user_id`` at ``business_id`` today.

    Counts ``pending`` submissions too — otherwise a volunteer could queue
    unlimited invoices and only later have them approved, bypassing the cap.
    """
    start = start_of_calendar_day()
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.business_id == business_id,
        Transaction.created_at >= start,
        Transaction.status.in_(COUNTED_STATUSES),
    )
    return int(db.scalar(stmt) or 0)


def count_uses_today_total(db: Session, user_id: int) -> int:
    """All successful submissions by ``user_id`` today, across every partner."""
    start = start_of_calendar_day()
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= start,
        Transaction.status.in_(COUNTED_STATUSES),
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
        Transaction.status.in_(COUNTED_STATUSES),
    )
    return int(db.scalar(stmt) or 0)


def pending_rewards(db: Session, user_id: int) -> int:
    """Reward points sitting in the review queue for ``user_id``.

    These are *not* spendable — they only become ``user.reward_points`` once an
    admin approves them.
    """
    stmt = select(func.coalesce(func.sum(Transaction.reward_increment), 0)).where(
        Transaction.user_id == user_id,
        Transaction.status == STATUS_PENDING,
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
    receipt_path: str | None = None,
    receipt_sha256: str | None = None,
    requires_receipt: bool = True,
    settings: Settings | None = None,
) -> Transaction:
    """Create a transaction for a verified invoice, enforcing every gate.

    With ``requires_receipt=True`` (Tier 2, the default) the row lands as
    ``pending`` and **no reward is credited** — that happens in
    :func:`approve_transaction` once an admin has seen the receipt. With
    ``requires_receipt=False`` (the documented Tier-1 fallback, driven by
    ``REQUIRE_RECEIPT_REVIEW``) the row is written straight to ``approved`` and
    the reward is credited immediately, preserving the old behaviour.

    Raises ``InvoiceFormatError`` (400) for implausible invoice numbers,
    ``DuplicateInvoiceError`` (409) for an invoice already credited at this
    partner (or a receipt image already seen there),
    ``DailyLimitExceededError`` (429) once this business is used
    ``DAILY_LIMIT_PER_BUSINESS`` times today, and
    ``TotalDailyLimitExceededError`` (429) once the all-partners ceiling is
    reached.
    """
    settings = settings or get_settings()
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

    # --- 2b. the same receipt *image* cannot credit a second invoice ---------
    # Without this, one photo could back any number of fabricated invoice
    # numbers at the same partner.
    if receipt_sha256 is not None:
        reused = db.scalar(
            select(Transaction.id).where(
                Transaction.business_id == business.id,
                Transaction.receipt_sha256 == receipt_sha256,
            )
        )
        if reused is not None:
            raise DuplicateInvoiceError(
                "This receipt image has already been submitted at this partner."
            )

    # --- 3. per-business daily limit ----------------------------------------
    used_today = count_uses_today(db, user.id, business.id)
    if used_today >= settings.DAILY_LIMIT_PER_BUSINESS:
        raise DailyLimitExceededError

    # --- 4. total daily limit across all partners ---------------------------
    if count_uses_today_total(db, user.id) >= settings.DAILY_LIMIT_TOTAL:
        raise TotalDailyLimitExceededError

    # --- create --------------------------------------------------------------
    review_required = requires_receipt
    transaction = Transaction(
        user_id=user.id,
        business_id=business.id,
        invoice_number=invoice,
        reward_increment=1,
        status=STATUS_PENDING if review_required else STATUS_APPROVED,
        receipt_path=receipt_path,
        receipt_sha256=receipt_sha256,
        reviewed_at=None if review_required else datetime.now(timezone.utc),
    )
    db.add(transaction)

    if not review_required:
        # Tier-1 fallback only: instant credit, exactly as before Tier 2.
        user.reward_points += transaction.reward_increment
        db.add(user)

    db.commit()
    db.refresh(transaction)
    return transaction


# --- review lifecycle ---------------------------------------------------------


def get_transaction_or_404(db: Session, transaction_id: int) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise TransactionNotFoundError
    return transaction


def approve_transaction(
    db: Session, *, admin: Admin, transaction: Transaction
) -> Transaction:
    """Approve a pending submission: credit the reward and audit the decision.

    This is the only place (besides the Tier-1 fallback and a manual admin
    adjustment) that changes ``reward_points``. Re-approving an already
    reviewed row is a conflict rather than a second credit.
    """
    if transaction.status != STATUS_PENDING:
        raise TransactionNotPendingError(
            f"This submission was already {transaction.status}."
        )

    user = db.get(User, transaction.user_id)
    if user is None:  # pragma: no cover — the FK guarantees it
        raise TransactionNotFoundError("The submitting volunteer no longer exists.")

    transaction.status = STATUS_APPROVED
    transaction.reviewed_by = admin.id
    transaction.reviewed_at = datetime.now(timezone.utc)
    transaction.rejection_reason = None
    user.reward_points += transaction.reward_increment

    db.add(transaction)
    db.add(user)
    db.add(
        RewardAdjustment(
            user_id=user.id,
            admin_id=admin.id,
            delta=transaction.reward_increment,
            reason=f"invoice approval #{transaction.id}",
        )
    )
    db.commit()
    db.refresh(transaction)
    return transaction


def reject_transaction(
    db: Session, *, admin: Admin, transaction: Transaction, reason: str | None = None
) -> Transaction:
    """Reject a pending submission. ``reward_points`` is never touched."""
    if transaction.status != STATUS_PENDING:
        raise TransactionNotPendingError(
            f"This submission was already {transaction.status}."
        )

    transaction.status = STATUS_REJECTED
    transaction.reviewed_by = admin.id
    transaction.reviewed_at = datetime.now(timezone.utc)
    transaction.rejection_reason = (reason or "").strip() or None

    db.add(transaction)
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


def paginate_for_review(
    db: Session,
    *,
    status: str | None = STATUS_PENDING,
    page: int = 1,
    page_size: int = 12,
) -> tuple[list[Transaction], int]:
    """Paginated review queue, **oldest first** so nothing is starved.

    ``status=None`` returns every status (the admin "all" filter).
    """
    stmt = select(Transaction)
    count_stmt = select(func.count(Transaction.id))
    if status is not None:
        stmt = stmt.where(Transaction.status == status)
        count_stmt = count_stmt.where(Transaction.status == status)

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            stmt.order_by(Transaction.created_at.asc(), Transaction.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total