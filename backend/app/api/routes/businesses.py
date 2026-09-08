"""Public business directory routes."""
from __future__ import annotations

import math

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.core.errors import BusinessNotFoundError
from app.models import Business
from app.schemas.business import (
    AreaOut,
    BusinessAreaOut,
    BusinessDetail,
    BusinessSummary,
    CategoryOut,
)
from app.schemas.common import Page
from app.schemas.transaction import TransactionOut
from app.services import businesses as business_service
from app.services import transactions as tx_service

router = APIRouter(prefix="/businesses", tags=["Businesses"])


@router.get("", response_model=Page[BusinessSummary])
def list_businesses(
    db: DbSession,
    category: str | None = Query(None, description="Category slug"),
    area_id: int | None = Query(None, ge=1),
    q: str | None = Query(None, description="Search by name/description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
):
    """Public catalog of participating merchants, filterable by category,
    area, or keyword. Only active partnerships are shown."""
    items, total = business_service.list_businesses(
        db,
        category_slug=category,
        area_id=area_id,
        search=q,
        page=page,
        page_size=page_size,
    )
    area_names = business_service.area_names_for(db, [b.id for b in items])
    return Page[BusinessSummary](
        items=[
            BusinessSummary(
                id=b.id,
                name=b.name,
                logo_url=b.logo_path,
                category_name=b.category.name if b.category else None,
                discount_percentage=b.discount_percentage,
                areas=area_names.get(b.id, []),
            )
            for b in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession):
    """All merchant categories (for filters)."""
    return [
        CategoryOut(id=c.id, name=c.name, slug=c.slug, description=c.description)
        for c in business_service.list_categories(db)
    ]


@router.get("/areas", response_model=list[AreaOut])
def list_areas(db: DbSession):
    """All geographic areas (for filters)."""
    return [AreaOut(id=a.id, name=a.name) for a in business_service.list_areas(db)]


@router.get("/{business_id}", response_model=BusinessDetail)
def business_detail(business_id: int, db: DbSession):
    """Detail view: discount %, logo, branch areas and partnership status."""
    business = db.get(Business, business_id)
    if business is None:
        raise BusinessNotFoundError
    return BusinessDetail(
        id=business.id,
        name=business.name,
        commercial_registration=business.commercial_registration,
        logo_url=business.logo_path,
        category_id=business.category_id,
        category_name=business.category.name if business.category else None,
        discount_percentage=business.discount_percentage,
        description=business.description,
        is_active=business.is_active,
        expiry_date=business.expiry_date,
        areas=[
            BusinessAreaOut(
                id=ba.id,
                area_id=ba.area_id,
                area_name=ba.area.name if ba.area else None,
                branch_name=ba.branch_name,
                address=ba.address,
                phone=ba.phone,
            )
            for ba in business.areas
        ],
    )


@router.get("/{business_id}/transactions", response_model=Page[TransactionOut])
def business_transactions(
    business_id: int,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """Paginated public transaction history for a business."""
    business = db.get(Business, business_id)
    if business is None:
        raise BusinessNotFoundError
    items, total = tx_service.paginate_transactions(
        db,
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