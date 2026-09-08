"""Admin control-center schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel
from app.schemas.user import UserProfile


class AdminCreateRequest(BaseModel):
    cpr: str = Field(min_length=5, max_length=20)
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(None, max_length=30)
    password: str = Field(min_length=8, max_length=72)
    expiry_date: datetime
    reward_points: int = Field(0, ge=0)


class AdminUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    is_active: bool | None = None
    expiry_date: datetime | None = None


class RewardAdjustmentRequest(BaseModel):
    """Manual reward counter adjustment: ``delta`` can be negative."""

    delta: int = Field(..., ge=-100_000, le=100_000)
    reason: str = Field(min_length=2, max_length=255)


class ExpiryOverrideRequest(BaseModel):
    expiry_date: datetime


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=72)


class AdminLogEntry(ORMModel):
    id: int
    transaction_id: int | None = None
    delta: int
    reason: str
    created_at: datetime


class AdminUserOut(UserProfile):
    """User record as seen by the admin (superset of the public profile)."""

    total_transactions: int = 0
    total_rewards: int = 0


class MostFrequentedBusiness(BaseModel):
    business_id: int
    business_name: str
    category_name: str | None = None
    count: int


class UserAnalytics(BaseModel):
    user: UserProfile
    total_transactions: int
    total_rewards_today: int = 0
    total_rewards_all_time: int
    most_frequented_business: MostFrequentedBusiness | None = None
    favorite_category: str | None = None
    last_activity: datetime | None = None
    recent_transactions: list[dict] = []


class DashboardMetrics(BaseModel):
    total_users: int
    active_users: int
    expired_users: int
    total_businesses: int
    total_transactions: int
    transactions_today: int
    total_rewards_awarded: int
    recent_transactions: list[dict] = []