"""Admin control-center service: user management, analytics, ledger.

Every manual reward-counter change is appended to the ``reward_adjustments``
audit log so all modifications are traceable by the organization.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import CprConflictError, EmailConflictError
from app.core.security import hash_password
from app.models import (
    Business,
    RewardAdjustment,
    Transaction,
    User,
)
from app.services.transactions import (
    start_of_calendar_day,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- user CRUD ---------------------------------------------------------------


def create_user(
    db: Session,
    *,
    cpr: str,
    email: str,
    name: str,
    phone: str | None,
    password: str,
    expiry_date: datetime,
    reward_points: int = 0,
    must_change_password: bool = True,
) -> User:
    if db.scalar(select(User).where(User.cpr == cpr)) is not None:
        raise CprConflictError
    if db.scalar(select(User).where(User.email == email.lower())) is not None:
        raise EmailConflictError
    user = User(
        cpr=cpr,
        email=email.lower(),
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        expiry_date=expiry_date,
        reward_points=reward_points,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    *,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    is_active: bool | None = None,
    expiry_date: datetime | None = None,
) -> User:
    if email is not None and email.lower() != user.email:
        existing = db.scalar(
            select(User).where(User.email == email.lower(), User.id != user.id)
        )
        if existing is not None:
            raise EmailConflictError
        user.email = email.lower()
    if name is not None:
        user.name = name
    if phone is not None:
        user.phone = phone.strip() or None
    if is_active is not None:
        user.is_active = is_active
    if expiry_date is not None:
        user.expiry_date = expiry_date
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    # Force the user to change it again on their next login.
    user.must_change_password = True
    # Invalidate all active sessions so the new password is required everywhere.
    user.token_version += 1
    db.add(user)
    db.commit()


def adjust_rewards(db: Session, user: User, delta: int, reason: str, admin_id: int) -> None:
    """Manually adjust the reward counter (delta may be negative) + audit."""
    adjustment = RewardAdjustment(
        user_id=user.id,
        admin_id=admin_id,
        delta=delta,
        reason=reason,
    )
    user.reward_points = max(0, user.reward_points + delta)
    db.add(adjustment)
    db.add(user)
    db.commit()
    db.refresh(user)


def set_expiry(db: Session, user: User, expiry_date: datetime) -> None:
    user.expiry_date = expiry_date
    db.add(user)
    db.commit()
    db.refresh(user)


def deactivate_user(db: Session, user: User) -> None:
    user.is_active = False
    user.token_version += 1  # kill existing sessions
    db.add(user)
    db.commit()


def activate_user(db: Session, user: User) -> None:
    user.is_active = True
    db.add(user)
    db.commit()


def list_users(
    db: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 12,
) -> tuple[list[User], int]:
    stmt = select(User)
    count_stmt = select(func.count(User.id))

    if search:
        like = f"%{search.strip()}%"
        condition = (User.name.ilike(like)) | (User.email.ilike(like)) | (User.cpr.ilike(like))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    if status == "active":
        cond = User.is_active.is_(True) & (User.expiry_date > _now())
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    elif status == "expired":
        cond = User.expiry_date <= _now()
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    elif status == "inactive":
        cond = User.is_active.is_(False)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            stmt.order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
    )
    return items, total


# --- analytics ---------------------------------------------------------------


def user_analytics(db: Session, user: User) -> dict:
    """Aggregate metrics for a single user (audit-trail support)."""
    total_transactions = int(
        db.scalar(select(func.count(Transaction.id)).where(Transaction.user_id == user.id)) or 0
    )
    today_start = start_of_calendar_day()
    rewards_today = int(
        db.scalar(
            select(func.coalesce(func.sum(Transaction.reward_increment), 0)).where(
                Transaction.user_id == user.id,
                Transaction.created_at >= today_start,
            )
        )
        or 0
    )

    # Most-frequented business + favourite category.
    row = db.execute(
        select(Transaction.business_id, func.count(Transaction.id).label("cnt"))
        .where(Transaction.user_id == user.id)
        .group_by(Transaction.business_id)
        .order_by(func.count(Transaction.id).desc())
        .limit(1)
    ).first()

    most_frequented = None
    favorite_category = None
    if row is not None:
        business = db.get(Business, row[0])
        if business is not None:
            most_frequented = {
                "business_id": business.id,
                "business_name": business.name,
                "category_name": business.category.name if business.category else None,
                "count": int(row[1]),
            }
            favorite_category = business.category.name if business.category else None

    last_activity = db.scalar(
        select(func.max(Transaction.created_at)).where(Transaction.user_id == user.id)
    )

    recent = list(
        db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(10)
        ).all()
    )

    return {
        "total_transactions": total_transactions,
        "total_rewards_today": rewards_today,
        "total_rewards_all_time": user.reward_points,
        "most_frequented_business": most_frequented,
        "favorite_category": favorite_category,
        "last_activity": last_activity,
        "recent_transactions": [
            {
                "id": t.id,
                "business_id": t.business_id,
                "business_name": t.business.name if t.business else None,
                "invoice_number": t.invoice_number,
                "reward_increment": t.reward_increment,
                "created_at": t.created_at,
            }
            for t in recent
        ],
    }


# --- dashboard ---------------------------------------------------------------


def dashboard_metrics(db: Session) -> dict:
    now = _now()
    today_start = start_of_calendar_day()

    total_users = int(db.scalar(select(func.count(User.id))) or 0)
    active_users = int(
        db.scalar(
            select(func.count(User.id)).where(
                User.is_active.is_(True), User.expiry_date > now
            )
        )
        or 0
    )
    expired_users = int(
        db.scalar(select(func.count(User.id)).where(User.expiry_date <= now)) or 0
    )
    total_businesses = int(db.scalar(select(func.count(Business.id))) or 0)
    total_transactions = int(db.scalar(select(func.count(Transaction.id))) or 0)
    transactions_today = int(
        db.scalar(
            select(func.count(Transaction.id)).where(Transaction.created_at >= today_start)
        )
        or 0
    )
    total_rewards = int(
        db.scalar(select(func.coalesce(func.sum(Transaction.reward_increment), 0))) or 0
    )

    recent = list(
        db.scalars(
            select(Transaction)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(10)
        ).all()
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "expired_users": expired_users,
        "total_businesses": total_businesses,
        "total_transactions": total_transactions,
        "transactions_today": transactions_today,
        "total_rewards_awarded": total_rewards,
        "recent_transactions": [
            {
                "id": t.id,
                "user_id": t.user_id,
                "user_name": t.user.name if t.user else None,
                "business_id": t.business_id,
                "business_name": t.business.name if t.business else None,
                "invoice_number": t.invoice_number,
                "reward_increment": t.reward_increment,
                "created_at": t.created_at,
            }
            for t in recent
        ],
    }


# --- ledger ------------------------------------------------------------------


def transaction_ledger(
    db: Session,
    *,
    search: str | None = None,
    user_id: int | None = None,
    business_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Transaction], int]:
    """Master transaction ledger with filters + pagination (newest first)."""
    stmt = select(Transaction)
    count_stmt = select(func.count(Transaction.id))

    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.join(Business, Transaction.business_id == Business.id).where(
            (Transaction.invoice_number.ilike(like)) | (Business.name.ilike(like))
        )
        count_stmt = count_stmt.join(Business, Transaction.business_id == Business.id).where(
            (Transaction.invoice_number.ilike(like)) | (Business.name.ilike(like))
        )
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
        ).unique().all()
    )
    return items, total