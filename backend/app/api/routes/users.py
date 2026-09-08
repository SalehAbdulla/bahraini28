"""Volunteer portal routes: profile, membership status and personal history."""
from __future__ import annotations

import math

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.models import Transaction
from app.schemas.common import Page
from app.schemas.transaction import TransactionOut
from app.schemas.user import UpdateMeRequest, UserProfile
from app.services import businesses as business_service
from app.services import transactions as tx_service
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfile)
def get_my_profile(user: CurrentUser):
    """Personal credentials, membership status, and reward balance."""
    return user


@router.patch("/me", response_model=UserProfile)
def update_my_profile(payload: UpdateMeRequest, user: CurrentUser, db: DbSession):
    """Update the volunteer's own name/email/phone."""
    updated = user_service.update_me(
        db,
        user=user,
        name=payload.name,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
    )
    return updated


@router.get("/me/transactions", response_model=Page[TransactionOut])
def my_transactions(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Paginated personal usage history (most recent first)."""
    items, total = tx_service.paginate_transactions(
        db,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )
    return _tx_page(items, total, page, page_size)


def _tx_page(
    items: list[Transaction],
    total: int,
    page: int,
    page_size: int,
) -> Page[TransactionOut]:
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