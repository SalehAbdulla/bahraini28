"""Business directory service."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessNotFoundError
from app.models import Area, Business, BusinessArea, Category


def list_businesses(
    db: Session,
    *,
    category_slug: str | None = None,
    area_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 12,
    include_inactive: bool = False,
) -> tuple[list[Business], int]:
    """Paginated public directory filtered by category, area or keyword."""
    base = select(Business)
    count_stmt = select(func.count(Business.id))

    if not include_inactive:
        base = base.where(Business.is_active.is_(True))
        count_stmt = count_stmt.where(Business.is_active.is_(True))

    if category_slug:
        base = base.join(Category, Business.category_id == Category.id).where(
            Category.slug == category_slug
        )
        count_stmt = count_stmt.join(Category, Business.category_id == Category.id).where(
            Category.slug == category_slug
        )

    if search:
        like = f"%{search.strip()}%"
        base = base.where(or_(Business.name.ilike(like), Business.description.ilike(like)))
        count_stmt = count_stmt.where(
            or_(Business.name.ilike(like), Business.description.ilike(like))
        )

    if area_id is not None:
        base = base.where(
            Business.id.in_(select(BusinessArea.business_id).where(BusinessArea.area_id == area_id))
        )
        count_stmt = count_stmt.where(
            Business.id.in_(select(BusinessArea.business_id).where(BusinessArea.area_id == area_id))
        )

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            base.order_by(Business.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
    )
    return items, total


def get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise BusinessNotFoundError
    return business


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name.asc())).all())


def list_areas(db: Session) -> list[Area]:
    return list(db.scalars(select(Area).where(Area.is_active.is_(True)).order_by(Area.name.asc())).all())


def area_names_for(db: Session, business_ids: list[int]) -> dict[int, list[str]]:
    """Map business_id -> sorted area names (used by list serialization).

    Runs a single query per request (no N+1, no extra connections).
    """
    if not business_ids:
        return {}
    rows = db.execute(
        select(BusinessArea.business_id, Area.name)
        .join(Area, BusinessArea.area_id == Area.id)
        .where(BusinessArea.business_id.in_(business_ids))
    ).all()
    mapping: dict[int, list[str]] = {}
    for business_id, name in rows:
        mapping.setdefault(business_id, []).append(name)
    for names in mapping.values():
        names.sort()
    return mapping