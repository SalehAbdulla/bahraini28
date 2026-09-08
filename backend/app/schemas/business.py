"""Business directory schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class BusinessAreaOut(ORMModel):
    id: int
    area_id: int
    area_name: str
    branch_name: str | None = None
    address: str | None = None
    phone: str | None = None


class BusinessDetail(ORMModel):
    id: int
    name: str
    commercial_registration: str
    logo_url: str | None = None
    category_id: int
    category_name: str
    discount_percentage: int
    description: str | None = None
    is_active: bool
    expiry_date: datetime
    areas: list[BusinessAreaOut] = []


class BusinessSummary(ORMModel):
    id: int
    name: str
    logo_url: str | None = None
    category_name: str
    discount_percentage: int
    areas: list[str] = []


class CategoryOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None = None


class AreaOut(ORMModel):
    id: int
    name: str