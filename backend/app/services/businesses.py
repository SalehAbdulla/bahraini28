"""Business directory service (public + admin management)."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import (
    AreaNotFoundError,
    BusinessExistsError,
    BusinessNotFoundError,
    CategoryNotFoundError,
)
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


def get_business_full(db: Session, business_id: int) -> Business:
    """Load a business with its category and branches eagerly populated."""
    business = db.scalar(
        select(Business)
        .options(selectinload(Business.areas).joinedload(BusinessArea.area))
        .options(joinedload(Business.category))
        .where(Business.id == business_id)
    )
    if business is None:
        raise BusinessNotFoundError
    return business


# --- Admin management ---------------------------------------------------------


def _validate_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise CategoryNotFoundError


def _area_id_of(branch) -> int | None:
    """Works for schema objects and ``model_dump()`` dicts (update path)."""
    return branch["area_id"] if isinstance(branch, dict) else branch.area_id


def _validate_areas(db: Session, branches) -> None:
    area_ids = {_area_id_of(b) for b in branches if _area_id_of(b)}
    if not area_ids:
        return
    found = set(db.scalars(select(Area.id).where(Area.id.in_(area_ids))).all())
    missing = sorted(area_ids - found)
    if missing:
        raise AreaNotFoundError(f"Area(s) not found: {missing}")


def _add_branches(db: Session, business_id: int, branches) -> None:
    for branch in branches:
        if isinstance(branch, dict):
            spec = {
                "area_id": branch["area_id"],
                "branch_name": branch.get("branch_name"),
                "address": branch.get("address"),
                "phone": branch.get("phone"),
            }
        else:
            spec = {
                "area_id": branch.area_id,
                "branch_name": branch.branch_name,
                "address": branch.address,
                "phone": branch.phone,
            }
        db.add(
            BusinessArea(
                business_id=business_id,
                area_id=spec["area_id"],
                branch_name=spec["branch_name"],
                address=spec["address"],
                phone=spec["phone"],
            )
        )


def create_business(
    db: Session,
    *,
    name: str,
    commercial_registration: str,
    category_id: int,
    discount_percentage: int,
    description: str | None,
    expiry_date,
    is_active: bool = True,
    branches: list | None = None,
) -> Business:
    """Register a new merchant partnership."""
    if db.scalar(
        select(Business).where(Business.commercial_registration == commercial_registration)
    ):
        raise BusinessExistsError
    _validate_category(db, category_id)
    branches = branches or []
    _validate_areas(db, branches)

    business = Business(
        name=name,
        commercial_registration=commercial_registration,
        category_id=category_id,
        discount_percentage=discount_percentage,
        description=description,
        expiry_date=expiry_date,
        is_active=is_active,
    )
    db.add(business)
    db.flush()
    _add_branches(db, business.id, branches)
    db.commit()
    db.expire(business)  # force fresh relationship data for serialization
    return business


def update_business(db: Session, business: Business, changes: dict) -> Business:
    """Apply partial changes (``branches`` replaces the full branch list)."""
    new_cr = changes.get("commercial_registration")
    if new_cr and new_cr != business.commercial_registration:
        conflict = db.scalar(
            select(Business).where(
                Business.commercial_registration == new_cr,
                Business.id != business.id,
            )
        )
        if conflict:
            raise BusinessExistsError

    new_category = changes.get("category_id")
    if new_category is not None:
        _validate_category(db, new_category)

    branches = changes.get("branches")
    if branches is not None:
        _validate_areas(db, branches)

    for field in (
        "name",
        "commercial_registration",
        "category_id",
        "discount_percentage",
        "description",
        "expiry_date",
        "is_active",
    ):
        if changes.get(field) is not None:
            setattr(business, field, changes[field])

    if branches is not None:
        business.areas.clear()  # cascade all, delete-orphan removes old branches
        db.flush()
        _add_branches(db, business.id, branches)

    db.commit()
    db.expire(business)  # force fresh relationship data for serialization
    return business


def list_managed_businesses(
    db: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Business], int]:
    """Paginated list including inactive, expired or draft partnerships."""
    base = select(Business)
    count_stmt = select(func.count(Business.id))

    if search:
        like = f"%{search.strip()}%"
        condition = or_(
            Business.name.ilike(like),
            Business.commercial_registration.ilike(like),
            Business.description.ilike(like),
        )
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)

    if status == "active":
        base = base.where(Business.is_active.is_(True))
        count_stmt = count_stmt.where(Business.is_active.is_(True))
    elif status == "inactive":
        base = base.where(Business.is_active.is_(False))
        count_stmt = count_stmt.where(Business.is_active.is_(False))

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            base.options(selectinload(Business.areas).joinedload(BusinessArea.area))
            .options(joinedload(Business.category))
            .order_by(Business.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


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