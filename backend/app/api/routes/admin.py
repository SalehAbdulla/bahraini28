"""Admin control-center routes: user management, analytics, ledger."""
from __future__ import annotations

import math

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.models import User
from app.schemas.admin import (
    AdminCreateRequest,
    AdminUpdateRequest,
    AdminUserOut,
    DashboardMetrics,
    ExpiryOverrideRequest,
    ResetPasswordRequest,
    RewardAdjustmentRequest,
    UserAnalytics,
)
from app.schemas.common import Page
from app.schemas.transaction import TransactionOut
from app.services import admin as admin_service
from app.services import users as user_service

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
            )
            for t in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )