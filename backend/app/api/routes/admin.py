"""Admin control-center routes: user management, analytics, ledger, businesses."""
from __future__ import annotations

import math
from pathlib import Path

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import AppSettings, CurrentAdmin, DbSession
from app.models import Business, Transaction, User
from app.schemas.admin import (
    AdminCreateRequest,
    AdminPasswordChangeRequest,
    AdminUpdateRequest,
    AdminUserOut,
    DashboardMetrics,
    ExpiryOverrideRequest,
    ResetPasswordRequest,
    RewardAdjustmentRequest,
    UserAnalytics,
)
from app.schemas.business import (
    AdminAreaOut,
    AdminBusinessCreate,
    AdminBusinessOut,
    AdminBusinessUpdate,
    AreaCreate,
    AreaUpdate,
    BusinessBranchOut,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    InvoiceCodeBatchCreate,
    InvoiceCodeBatchOut,
    InvoiceCodeOut,
    InvoiceCodeStats,
)
from app.schemas.common import Page
from app.schemas.transaction import (
    RejectTransactionRequest,
    TransactionOut,
    TransactionReviewOut,
)
from app.services import admin as admin_service
from app.services import businesses as business_service
from app.services import invoice_codes as code_service
from app.services import transactions as tx_service
from app.services import users as user_service
from app.services.notifications import bus
from app.services.uploads import ALLOWED_IMAGE_TYPES, store_upload

router = APIRouter(prefix="/admin", tags=["Admin"])


def _admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        cpr=user.cpr,
        email=user.email,
        name=user.name,
        phone=user.phone,
        expiry_date=user.expiry_date,
        is_active=user.is_active,
        reward_points=user.reward_points,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
    )


@router.post("/me/password", status_code=204)
def change_own_password(
    payload: AdminPasswordChangeRequest, db: DbSession, admin: CurrentAdmin
):
    """Rotate the signed-in admin's own password (the current one is required).

    Admins are exempt from session invalidation, so other open admin tabs keep
    working. For a *forgotten* password use ``scripts/set_admin_password.py``,
    which is what the deployment runbook points at.
    """
    admin_service.change_admin_password(
        db,
        admin,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


@router.get("/metrics", response_model=DashboardMetrics)
def dashboard_metrics(db: DbSession, admin: CurrentAdmin):
    """Global KPIs for the admin dashboard."""
    return DashboardMetrics(**admin_service.dashboard_metrics(db))


@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    db: DbSession,
    admin: CurrentAdmin,
    search: str | None = Query(None),
    status: str | None = Query(None, pattern="^(active|expired|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
):
    """Paginated user list with search + status filters (audit trail)."""
    items, total = admin_service.list_users(
        db, search=search, status=status, page=page, page_size=page_size
    )
    return Page[AdminUserOut](
        items=[_admin_user_out(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(payload: AdminCreateRequest, db: DbSession, admin: CurrentAdmin):
    """Add a new volunteer account (expiry date, initial password, rewards)."""
    user = admin_service.create_user(
        db,
        cpr=payload.cpr,
        email=str(payload.email),
        name=payload.name,
        phone=payload.phone,
        password=payload.password,
        expiry_date=payload.expiry_date,
        reward_points=payload.reward_points,
    )
    return _admin_user_out(user)


@router.get("/users/{user_id}", response_model=AdminUserOut)
def get_user(user_id: int, db: DbSession, admin: CurrentAdmin):
    user = user_service.get_or_404(db, user_id)
    return _admin_user_out(user)


@router.get("/users/{user_id}/analytics", response_model=UserAnalytics)
def user_analytics(user_id: int, db: DbSession, admin: CurrentAdmin):
    """Detailed analytics for one user: history, aggregates, favourites."""
    user = user_service.get_or_404(db, user_id)
    analytics = admin_service.user_analytics(db, user)
    return UserAnalytics(
        user=_profile(user),
        total_transactions=analytics["total_transactions"],
        total_rewards_today=analytics["total_rewards_today"],
        total_rewards_all_time=analytics["total_rewards_all_time"],
        most_frequented_business=analytics["most_frequented_business"],
        favorite_category=analytics["favorite_category"],
        last_activity=analytics["last_activity"],
        recent_transactions=analytics["recent_transactions"],
    )


def _profile(user: User):
    from app.schemas.user import UserProfile

    return UserProfile(
        id=user.id,
        cpr=user.cpr,
        email=user.email,
        name=user.name,
        phone=user.phone,
        expiry_date=user.expiry_date,
        is_active=user.is_active,
        reward_points=user.reward_points,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
    )


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUpdateRequest,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Modify user details (name/email/phone/status/expiry)."""
    user = user_service.get_or_404(db, user_id)
    updated = admin_service.update_user(
        db,
        user=user,
        name=payload.name,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        is_active=payload.is_active,
        expiry_date=payload.expiry_date,
    )
    return _admin_user_out(updated)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
def deactivate_user(user_id: int, db: DbSession, admin: CurrentAdmin):
    """Deactivate a user account and invalidate all of its sessions."""
    user = user_service.get_or_404(db, user_id)
    admin_service.deactivate_user(db, user)
    return _admin_user_out(user)


@router.post("/users/{user_id}/activate", response_model=AdminUserOut)
def activate_user(user_id: int, db: DbSession, admin: CurrentAdmin):
    """Re-activate a previously deactivated user account."""
    user = user_service.get_or_404(db, user_id)
    admin_service.activate_user(db, user)
    return _admin_user_out(user)


@router.put("/users/{user_id}/expiry", response_model=AdminUserOut)
def override_expiry(
    user_id: int,
    payload: ExpiryOverrideRequest,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Override the membership expiry date."""
    user = user_service.get_or_404(db, user_id)
    admin_service.set_expiry(db, user, payload.expiry_date)
    return _admin_user_out(user)


@router.put("/users/{user_id}/reward", response_model=AdminUserOut)
def adjust_reward(
    user_id: int,
    payload: RewardAdjustmentRequest,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Manually adjust the reward counter (delta may be negative). Audited."""
    user = user_service.get_or_404(db, user_id)
    admin_service.adjust_rewards(
        db,
        user=user,
        delta=payload.delta,
        reason=payload.reason,
        admin_id=admin.id,
    )
    return _admin_user_out(user)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserOut)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Reset a user's password; forces a change on next login and invalidates
    all active sessions."""
    user = user_service.get_or_404(db, user_id)
    admin_service.reset_password(db, user, payload.new_password)
    return _admin_user_out(user)


@router.get("/transactions", response_model=Page[TransactionOut])
def transaction_ledger(
    db: DbSession,
    admin: CurrentAdmin,
    search: str | None = Query(None),
    user_id: int | None = Query(None, ge=1),
    business_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Master transaction ledger showing invoice numbers (paginated)."""
    items, total = admin_service.transaction_ledger(
        db,
        search=search,
        user_id=user_id,
        business_id=business_id,
        page=page,
        page_size=page_size,
    )
    return Page[TransactionOut](
        items=[
            TransactionOut(
                id=t.id,
                business_id=t.business_id,
                business_name=t.business.name if t.business else None,
                invoice_number=t.invoice_number,
                reward_increment=t.reward_increment,
                created_at=t.created_at,
                status=t.status,
                code=t.code.code if t.code else None,
                rejection_reason=t.rejection_reason,
            )
            for t in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


# --- Invoice review queue (Tier 2) --------------------------------------------


def _review_out(t: Transaction) -> TransactionReviewOut:
    return TransactionReviewOut(
        id=t.id,
        business_id=t.business_id,
        business_name=t.business.name if t.business else None,
        invoice_number=t.invoice_number,
        reward_increment=t.reward_increment,
        created_at=t.created_at,
        status=t.status,
        code=t.code.code if t.code else None,
        rejection_reason=t.rejection_reason,
        user_id=t.user_id,
        user_name=t.user.name if t.user else None,
        receipt_url=t.receipt_path,
        reviewed_at=t.reviewed_at,
    )


@router.get("/transactions/review", response_model=Page[TransactionReviewOut])
def review_queue(
    db: DbSession,
    admin: CurrentAdmin,
    status: str | None = Query("pending", pattern="^(pending|approved|rejected|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
):
    """Receipt-review queue — oldest submission first, so nothing is starved."""
    items, total = tx_service.paginate_for_review(
        db, status=None if status == "all" else status, page=page, page_size=page_size
    )
    return Page[TransactionReviewOut](
        items=[_review_out(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/transactions/{transaction_id}/approve", response_model=TransactionReviewOut)
async def approve_transaction(transaction_id: int, db: DbSession, admin: CurrentAdmin):
    """Approve a pending submission: credit the reward + write an audit row."""
    transaction = tx_service.get_transaction_or_404(db, transaction_id)
    transaction = tx_service.approve_transaction(db, admin=admin, transaction=transaction)
    await bus.publish(
        "invoice_reviewed",
        {
            "transaction_id": transaction.id,
            "status": transaction.status,
            "user_id": transaction.user_id,
            "reviewed_by": admin.id,
            "reviewed_at": transaction.reviewed_at,
        },
    )
    return _review_out(transaction)


@router.post("/transactions/{transaction_id}/reject", response_model=TransactionReviewOut)
async def reject_transaction(
    transaction_id: int,
    payload: RejectTransactionRequest,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Reject a pending submission. Reward points are never touched."""
    transaction = tx_service.get_transaction_or_404(db, transaction_id)
    transaction = tx_service.reject_transaction(
        db, admin=admin, transaction=transaction, reason=payload.reason
    )
    await bus.publish(
        "invoice_reviewed",
        {
            "transaction_id": transaction.id,
            "status": transaction.status,
            "user_id": transaction.user_id,
            "reviewed_by": admin.id,
            "reviewed_at": transaction.reviewed_at,
        },
    )
    return _review_out(transaction)


# --- Business management ------------------------------------------------------


def _admin_business_out(b: Business) -> AdminBusinessOut:
    return AdminBusinessOut(
        id=b.id,
        name=b.name,
        commercial_registration=b.commercial_registration,
        logo_url=b.logo_path,
        category_id=b.category_id,
        category_name=b.category.name if b.category else None,
        discount_percentage=b.discount_percentage,
        description=b.description,
        invoice_pattern=b.invoice_pattern,
        codes_required=b.codes_required,
        is_active=b.is_active,
        expiry_date=b.expiry_date,
        branches=[
            BusinessBranchOut(
                id=branch.id,
                area_id=branch.area_id,
                area_name=branch.area.name if branch.area else None,
                branch_name=branch.branch_name,
                address=branch.address,
                phone=branch.phone,
            )
            for branch in sorted(b.areas, key=lambda a: a.id)
        ],
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


@router.get("/businesses", response_model=Page[AdminBusinessOut])
def list_businesses(
    db: DbSession,
    admin: CurrentAdmin,
    search: str | None = Query(None),
    status: str | None = Query(None, pattern="^(active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Paginated business list incl. inactive/expired partnerships, with search
    by name, commercial registration or description."""
    items, total = business_service.list_managed_businesses(
        db, search=search, status=status, page=page, page_size=page_size
    )
    return Page[AdminBusinessOut](
        items=[_admin_business_out(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/businesses", response_model=AdminBusinessOut, status_code=201)
def create_business(
    payload: AdminBusinessCreate, db: DbSession, admin: CurrentAdmin
):
    """Register a new merchant partnership (category + optional branches)."""
    business = business_service.create_business(
        db,
        name=payload.name,
        commercial_registration=payload.commercial_registration,
        category_id=payload.category_id,
        discount_percentage=payload.discount_percentage,
        description=payload.description,
        expiry_date=payload.expiry_date,
        is_active=payload.is_active,
        branches=payload.branches,
        invoice_pattern=payload.invoice_pattern,
        codes_required=payload.codes_required,
    )
    return _admin_business_out(business_service.get_business_full(db, business.id))


@router.put("/businesses/{business_id}", response_model=AdminBusinessOut)
def update_business(
    business_id: int,
    payload: AdminBusinessUpdate,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Update a business; omit fields to keep current values, pass ``branches``
    (even empty) to replace the branch list."""
    business = business_service.get_business_or_404(db, business_id)
    changes = payload.model_dump(exclude_unset=True)
    business_service.update_business(db, business, changes)
    return _admin_business_out(business_service.get_business_full(db, business_id))


@router.post("/businesses/{business_id}/logo", response_model=AdminBusinessOut)
async def upload_business_logo(
    business_id: int,
    file: UploadFile = File(...),
    db: DbSession = None,  # type: ignore[assignment]
    admin: CurrentAdmin = None,  # type: ignore[assignment]
    settings: AppSettings = None,  # type: ignore[assignment]
):
    """Upload/replace a business logo (PNG/JPEG/GIF/WebP, size limited by
    ``MAX_UPLOAD_SIZE_MB``). The previous logo file is removed so old uploads
    don't accumulate. Files land in ``UPLOAD_DIR`` and are served at /uploads.
    """
    business = business_service.get_business_or_404(db, business_id)

    logo_url, _sha256 = await store_upload(
        file,
        settings=settings,
        allowed_types=ALLOWED_IMAGE_TYPES,
        prefix=f"b{business_id}",
        label="Logo",
    )

    if business.logo_path:
        old = Path(settings.UPLOAD_DIR) / Path(business.logo_path).name
        if old.exists():
            old.unlink()

    business.logo_path = logo_url
    db.commit()
    db.expire(business)
    return _admin_business_out(business_service.get_business_full(db, business_id))


# --- Anti-fraud Tier 3: single-use merchant receipt codes ----------------------


def _code_out(code) -> InvoiceCodeOut:
    return InvoiceCodeOut(
        id=code.id,
        business_id=code.business_id,
        code=code.code,
        status=code.status,
        batch=code.batch,
        created_at=code.created_at,
        claimed_at=code.claimed_at,
        redeemed_at=code.redeemed_at,
        claimed_by_user_id=code.claimed_by_user_id,
        claimed_by_user_name=code.claimed_by_user.name if code.claimed_by_user else None,
    )


@router.get("/businesses/{business_id}/codes", response_model=Page[InvoiceCodeOut])
def list_business_codes(
    business_id: int,
    db: DbSession,
    admin: CurrentAdmin,
    status: str | None = Query(
        None, pattern="^(issued|claimed|redeemed|revoked|all)$"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """The single-use codes issued to one partner (newest first)."""
    business_service.get_business_or_404(db, business_id)
    items, total = code_service.list_codes(
        db,
        business_id=business_id,
        status=None if status in (None, "all") else status,
        page=page,
        page_size=page_size,
    )
    return Page[InvoiceCodeOut](
        items=[_code_out(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/businesses/{business_id}/codes/stats", response_model=InvoiceCodeStats)
def business_code_stats(business_id: int, db: DbSession, admin: CurrentAdmin):
    """Lifecycle counts (issued / claimed / redeemed / revoked) for a partner."""
    business_service.get_business_or_404(db, business_id)
    return InvoiceCodeStats(**code_service.code_stats(db, business_id))


@router.post(
    "/businesses/{business_id}/codes",
    response_model=InvoiceCodeBatchOut,
    status_code=201,
)
def generate_business_codes(
    business_id: int,
    payload: InvoiceCodeBatchCreate,
    db: DbSession,
    admin: CurrentAdmin,
):
    """Mint a batch of single-use codes for a partner (returned so they can be
    printed straight away)."""
    business = business_service.get_business_or_404(db, business_id)
    codes = code_service.create_batch(
        db,
        business_id=business.id,
        count=payload.count,
        batch=payload.batch,
        admin_id=admin.id,
    )
    return InvoiceCodeBatchOut(items=[_code_out(c) for c in codes], created=len(codes))


@router.delete("/codes/{code_id}", response_model=InvoiceCodeOut)
def revoke_invoice_code(code_id: int, db: DbSession, admin: CurrentAdmin):
    """Revoke a code that was never claimed — e.g. a sheet that was lost."""
    code = code_service.get_code_or_404(db, code_id)
    return _code_out(code_service.revoke_code(db, code))


# --- Catalog management (areas & categories) ----------------------------------


@router.get("/areas", response_model=list[AdminAreaOut])
def list_areas(db: DbSession, admin: CurrentAdmin):
    """Every area (including deactivated ones) for the admin catalog view."""
    return [AdminAreaOut.model_validate(a) for a in business_service.list_all_areas(db)]


@router.post("/areas", response_model=AdminAreaOut, status_code=201)
def create_area(payload: AreaCreate, db: DbSession, admin: CurrentAdmin):
    """Add a new geographic area."""
    return AdminAreaOut.model_validate(business_service.create_area(db, name=payload.name))


@router.put("/areas/{area_id}", response_model=AdminAreaOut)
def update_area(
    area_id: int, payload: AreaUpdate, db: DbSession, admin: CurrentAdmin
):
    """Rename an area and/or toggle its active flag."""
    area = business_service.get_area_or_404(db, area_id)
    updated = business_service.update_area(db, area, payload.model_dump(exclude_unset=True))
    return AdminAreaOut.model_validate(updated)


@router.delete("/areas/{area_id}", status_code=204)
def delete_area(area_id: int, db: DbSession, admin: CurrentAdmin):
    """Delete an area; blocked while any business branch still references it."""
    area = business_service.get_area_or_404(db, area_id)
    business_service.delete_area(db, area)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession, admin: CurrentAdmin):
    """All merchant categories for the admin catalog view."""
    return [CategoryOut.model_validate(c) for c in business_service.list_categories(db)]


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: DbSession, admin: CurrentAdmin):
    """Add a new merchant category (slug auto-generated from the name)."""
    category = business_service.create_category(
        db, name=payload.name, slug=payload.slug, description=payload.description
    )
    return CategoryOut.model_validate(category)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, payload: CategoryUpdate, db: DbSession, admin: CurrentAdmin
):
    """Rename a category and/or update its slug/description."""
    category = business_service.get_category_or_404(db, category_id)
    updated = business_service.update_category(
        db, category, payload.model_dump(exclude_unset=True)
    )
    return CategoryOut.model_validate(updated)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: DbSession, admin: CurrentAdmin):
    """Delete a category; blocked while any business still references it."""
    category = business_service.get_category_or_404(db, category_id)
    business_service.delete_category(db, category)
