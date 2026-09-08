"""User schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserProfile(ORMModel):
    id: int
    cpr: str
    email: EmailStr
    name: str
    phone: str | None = None
    expiry_date: datetime
    is_active: bool
    reward_points: int
    must_change_password: bool
    created_at: datetime


class UpdateMeRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)