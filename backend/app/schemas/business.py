"""Business directory schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

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


# --- Admin business management -------------------------------------------------


class BusinessBranchIn(BaseModel):
    """One branch (area + optional branch details) attached to a business."""

    area_id: int = Field(gt=0)
    branch_name: str | None = Field(None, max_length=120)
    address: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)


class BusinessBranchOut(ORMModel):
    id: int
    area_id: int
    area_name: str
    branch_name: str | None = None
    address: str | None = None
    phone: str | None = None


class AdminBusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    commercial_registration: str = Field(min_length=3, max_length=60)
    category_id: int = Field(gt=0)
    discount_percentage: int = Field(ge=0, le=100)
    description: str | None = Field(None, max_length=2000)
    expiry_date: datetime
    is_active: bool = True
    branches: list[BusinessBranchIn] = []


class AdminBusinessUpdate(BaseModel):
    """All fields optional — omitted fields keep their current value. If
    ``branches`` is provided (even as an empty list) it replaces the full
    branch list."""

    name: str | None = Field(None, min_length=2, max_length=160)
    commercial_registration: str | None = Field(None, min_length=3, max_length=60)
    category_id: int | None = Field(None, gt=0)
    discount_percentage: int | None = Field(None, ge=0, le=100)
    description: str | None = None
    expiry_date: datetime | None = None
    is_active: bool | None = None
    branches: list[BusinessBranchIn] | None = None


class AdminBusinessOut(ORMModel):
    id: int
    name: str
    commercial_registration: str
    logo_url: str | None = None
    category_id: int
    category_name: str | None = None
    discount_percentage: int
    description: str | None = None
    is_active: bool
    expiry_date: datetime
    branches: list[BusinessBranchOut] = []
    created_at: datetime
    updated_at: datetime