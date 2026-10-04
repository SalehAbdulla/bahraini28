"""Invoice-code service (anti-fraud Tier 3) — issue batches, move the lifecycle.

This is the whole surface behind "a fabricated number simply never matches an
unused code":

* :func:`create_batch` — an admin mints N single-use codes for one partner;
* :func:`list_codes` / :func:`code_stats` — the admin reconciliation view;
* :func:`revoke_code` — cancel a code that was never handed out;
* :func:`claim_for_submission` / :func:`redeem` / :func:`release` — the lifecycle
  hooks the transaction service drives.

Claiming/redeeming/releasing deliberately do **not** commit: they are part of the
caller's transaction, so a submission that fails a later gate leaves the code
exactly as it found it.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import (
    InvalidInvoiceCodeError,
    InvoiceCodeNotFoundError,
    InvoiceCodeUsedError,
)
from app.models import InvoiceCode
from app.models.invoice_code import (
    CODE_CLAIMED,
    CODE_ISSUED,
    CODE_REDEEMED,
    CODE_REVOKED,
)

#: Ambiguity-free alphabet: no 0/O, 1/I/L — these codes are read off a paper
#: receipt and retyped by a volunteer.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
#: Shared, recognisable prefix so "this is a Bahraini 28 code" is obvious.
CODE_PREFIX = "B28"
#: ``B28-XXXX-XXXX`` — two groups of four characters (~40 bits of entropy).
_GROUP_SIZE = 4
_GROUP_COUNT = 2
#: Largest batch an admin may mint in a single request.
MAX_BATCH_SIZE = 500


def generate_code() -> str:
    """Return a fresh, human-readable code (``B28-XXXX-XXXX``)."""
    groups = [
        "".join(secrets.choice(CODE_ALPHABET) for _ in range(_GROUP_SIZE))
        for _ in range(_GROUP_COUNT)
    ]
    return "-".join([CODE_PREFIX, *groups])


def normalize_code(value: str) -> str:
    """Canonical form used for storage and lookup (trim + upper)."""
    return value.strip().upper()


def _unique_code(db: Session, taken: set[str]) -> str:
    """A code not already in the database *or* in this batch."""
    for _ in range(25):  # collisions are astronomically unlikely; bound anyway
        candidate = generate_code()
        if candidate in taken:
            continue
        if db.scalar(select(InvoiceCode.id).where(InvoiceCode.code == candidate)) is None:
            return candidate
    raise RuntimeError("Could not generate a unique invoice code.")  # pragma: no cover


def create_batch(
    db: Session,
    *,
    business_id: int,
    count: int,
    batch: str | None = None,
    admin_id: int | None = None,
) -> list[InvoiceCode]:
    """Mint ``count`` single-use codes for one partner.

    All of them land ``issued``; nothing is claimed until a volunteer submits one.
    """
    if count < 1:
        raise ValueError("A batch must contain at least one code.")
    if count > MAX_BATCH_SIZE:
        raise ValueError(f"A batch may contain at most {MAX_BATCH_SIZE} codes.")

    label = (batch or "").strip() or None
    taken: set[str] = set()
    codes: list[InvoiceCode] = []
    for _ in range(count):
        candidate = _unique_code(db, taken)
        taken.add(candidate)
        codes.append(
            InvoiceCode(
                business_id=business_id,
                code=candidate,
                status=CODE_ISSUED,
                batch=label,
                created_by=admin_id,
            )
        )

    db.add_all(codes)
    db.commit()
    for code in codes:
        db.refresh(code)
    return codes


def list_codes(
    db: Session,
    *,
    business_id: int,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[InvoiceCode], int]:
    """Paginated code list for one partner, newest first.

    ``status=None`` returns every status (the admin "all" filter).
    """
    stmt = (
        select(InvoiceCode)
        .where(InvoiceCode.business_id == business_id)
        .options(selectinload(InvoiceCode.claimed_by_user))
    )
    count_stmt = select(func.count(InvoiceCode.id)).where(
        InvoiceCode.business_id == business_id
    )
    if status is not None:
        stmt = stmt.where(InvoiceCode.status == status)
        count_stmt = count_stmt.where(InvoiceCode.status == status)

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            stmt.order_by(InvoiceCode.created_at.desc(), InvoiceCode.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def code_stats(db: Session, business_id: int) -> dict[str, int]:
    """Counts per lifecycle state (plus ``total``) for the partner's code view."""
    rows = db.execute(
        select(InvoiceCode.status, func.count(InvoiceCode.id))
        .where(InvoiceCode.business_id == business_id)
        .group_by(InvoiceCode.status)
    ).all()

    stats = {status: 0 for status in (CODE_ISSUED, CODE_CLAIMED, CODE_REDEEMED, CODE_REVOKED)}
    for status, count in rows:
        stats[status] = int(count)
    stats["total"] = sum(stats.values())
    return stats


def get_code_or_404(db: Session, code_id: int) -> InvoiceCode:
    code = db.get(InvoiceCode, code_id)
    if code is None:
        raise InvoiceCodeNotFoundError
    return code


def revoke_code(db: Session, code: InvoiceCode) -> InvoiceCode:
    """Cancel a code that has not been claimed or redeemed yet."""
    if code.status != CODE_ISSUED:
        raise InvoiceCodeUsedError(
            f"Only an unclaimed code can be revoked (this one is {code.status})."
        )
    code.status = CODE_REVOKED
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


# --- lifecycle (driven by the transaction service; no commit here) -------------


def claim_for_submission(
    db: Session, *, business_id: int, raw_code: str, user_id: int
) -> InvoiceCode:
    """Reserve an ``issued`` code for a submission at ``business_id``.

    Raises :class:`InvalidInvoiceCodeError` when the code does not exist or
    belongs to a different partner (a fabricated number never matches), and
    :class:`InvoiceCodeUsedError` when it has already been spent or is already
    held by another submission in the queue.
    """
    code = db.scalar(
        select(InvoiceCode).where(InvoiceCode.code == normalize_code(raw_code))
    )
    if code is None or code.business_id != business_id:
        raise InvalidInvoiceCodeError
    if code.status != CODE_ISSUED:
        raise InvoiceCodeUsedError

    code.status = CODE_CLAIMED
    code.claimed_by_user_id = user_id
    code.claimed_at = datetime.now(timezone.utc)
    code.redeemed_at = None
    db.add(code)
    return code


def redeem(db: Session, code: InvoiceCode) -> InvoiceCode:
    """Mark a claimed code as spent — the reward it proved has been credited."""
    code.status = CODE_REDEEMED
    code.redeemed_at = datetime.now(timezone.utc)
    db.add(code)
    return code


def release(db: Session, code: InvoiceCode) -> InvoiceCode:
    """Return a claimed code to the pool after a rejected submission.

    The volunteer keeps the physical receipt, so an honest mistake (an unclear
    photo) must not consume the only code they have.
    """
    code.status = CODE_ISSUED
    code.claimed_by_user_id = None
    code.claimed_at = None
    code.redeemed_at = None
    db.add(code)
    return code
