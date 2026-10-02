"""Transaction routes: invoice submission with a receipt (Tier 2) + daily limits.

The volunteer UI posts **multipart** (invoice fields + the receipt image). A
JSON body is still accepted so a deployment running the Tier-1 fallback
(``REQUIRE_RECEIPT_REVIEW=False``) can keep an older client working unchanged.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.errors import ReceiptRequiredError
from app.schemas.transaction import InvoiceSubmitRequest, TransactionCreatedOut
from app.services import transactions as tx_service
from app.services.notifications import bus
from app.services.uploads import ALLOWED_RECEIPT_TYPES, store_upload

router = APIRouter(prefix="/transactions", tags=["Transactions"])

_UNSUPPORTED_RECEIPT = "Unsupported receipt type. Use a PNG, JPEG or WebP image, or a PDF."


async def _read_submission(
    request: Request,
    business_id: int | None,
    invoice_number: str | None,
) -> tuple[int, str]:
    """Return ``(business_id, invoice_number)`` from multipart *or* JSON.

    Multipart is what the volunteer UI sends (it carries the receipt file); the
    JSON fallback keeps the Tier-1 contract alive for un-onboarded deployments.
    """
    if business_id is not None and invoice_number is not None:
        return business_id, invoice_number

    try:
        raw = await request.json()
    except Exception as exc:  # noqa: BLE001 - malformed/absent body
        raise RequestValidationError(
            [
                {
                    "loc": ("body",),
                    "msg": "Invalid or missing request body.",
                    "type": "value_error",
                }
            ]
        ) from exc
    try:
        payload = InvoiceSubmitRequest.model_validate(raw)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return payload.business_id, payload.invoice_number


@router.post("", response_model=TransactionCreatedOut, status_code=201)
async def submit_invoice(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    business_id: int | None = Form(None),
    invoice_number: str | None = Form(None),
    receipt: UploadFile | None = File(None),
):
    """Submit a physical-store invoice (plus receipt photo) to earn a reward.

    With ``REQUIRE_RECEIPT_REVIEW=True`` (default) the receipt is **required**
    and the row is stored as ``pending``: nothing is credited until an admin
    approves it. With ``False`` the receipt is optional and the reward is
    credited immediately (Tier 1 behaviour).
    """
    business_id, invoice_number = await _read_submission(
        request, business_id, invoice_number
    )

    review_required = settings.REQUIRE_RECEIPT_REVIEW
    if review_required and receipt is None:
        raise ReceiptRequiredError

    receipt_path: str | None = None
    receipt_sha256: str | None = None
    if receipt is not None:
        receipt_path, receipt_sha256 = await store_upload(
            receipt,
            settings=settings,
            allowed_types=ALLOWED_RECEIPT_TYPES,
            prefix=f"r{business_id}",
            label="Receipt",
            unsupported_message=_UNSUPPORTED_RECEIPT,
        )

    try:
        transaction = tx_service.submit_invoice(
            db,
            user=user,
            business_id=business_id,
            invoice_number=invoice_number,
            receipt_path=receipt_path,
            receipt_sha256=receipt_sha256,
            requires_receipt=review_required,
            settings=settings,
        )
    except Exception:
        # A gate rejected the submission — drop the just-written file rather
        # than leaving orphaned uploads behind.
        if receipt_path:
            (Path(settings.UPLOAD_DIR) / Path(receipt_path).name).unlink(missing_ok=True)
        raise

    used_today = tx_service.count_uses_today(db, user.id, transaction.business_id)
    remaining = max(0, settings.DAILY_LIMIT_PER_BUSINESS - used_today)
    used_today_total = tx_service.count_uses_today_total(db, user.id)
    remaining_total = max(0, settings.DAILY_LIMIT_TOTAL - used_today_total)

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
            "status": transaction.status,
            "created_at": transaction.created_at,
        },
    )

    # Anti-fraud signal: one account crediting an unusually high number of
    # *distinct* partners in a single day. Surfaced on the admin dashboard so a
    # human can review the ledger before more rewards are handed out.
    distinct_today = tx_service.count_distinct_businesses_today(db, user.id)
    if distinct_today >= settings.FRAUD_DISTINCT_BUSINESSES_PER_DAY:
        await bus.publish(
            "fraud_signal",
            {
                "user_id": user.id,
                "user_name": user.name,
                "distinct_businesses_today": distinct_today,
                "threshold": settings.FRAUD_DISTINCT_BUSINESSES_PER_DAY,
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
        status=transaction.status,
        rejection_reason=transaction.rejection_reason,
        used_today=used_today,
        remaining_today=remaining,
        used_today_total=used_today_total,
        remaining_today_total=remaining_total,
        reward_points_balance=user.reward_points,
    )