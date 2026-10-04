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
    invoice_pattern: str | None = None
    #: True when this partner prints single-use codes, so the submission form
    #: must ask for one (anti-fraud Tier 3).
    codes_required: bool = False
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


# --- Admin catalog management (areas & categories) -----------------------------


class AdminAreaOut(ORMModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime


class AreaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class AreaUpdate(BaseModel):
    """Omitted fields keep their current value."""

    name: str | None = Field(None, min_length=2, max_length=80)
    is_active: bool | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str | None = Field(None, min_length=2, max_length=80)
    description: str | None = Field(None, max_length=255)


class CategoryUpdate(BaseModel):
    """Omitted fields keep their current value."""

    name: str | None = Field(None, min_length=2, max_length=80)
    slug: str | None = Field(None, min_length=2, max_length=80)
    description: str | None = Field(None, max_length=255)



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
    invoice_pattern: str | None = Field(None, max_length=160)
    expiry_date: datetime
    is_active: bool = True
    #: Opt the partner into Tier 3: submissions must quote an issued code.
    codes_required: bool = False
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
    invoice_pattern: str | None = Field(None, max_length=160)
    expiry_date: datetime | None = None
    is_active: bool | None = None
    codes_required: bool | None = None
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
    invoice_pattern: str | None = None
    codes_required: bool = False
    is_active: bool
    expiry_date: datetime
    branches: list[BusinessBranchOut] = []
    created_at: datetime
    updated_at: datetime


# --- Anti-fraud Tier 3: single-use merchant receipt codes ----------------------


class InvoiceCodeBatchCreate(BaseModel):
    """Mint ``count`` single-use codes for one partner."""

    count: int = Field(5, ge=1, le=500)
    #: Optional label so a printed sheet can be traced to the batch it came from.
    batch: str | None = Field(None, max_length=60)


class InvoiceCodeOut(ORMModel):
    id: int
    business_id: int
    code: str
    #: ``issued`` | ``claimed`` | ``redeemed`` | ``revoked``.
    status: str
    batch: str | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    redeemed_at: datetime | None = None
    claimed_by_user_id: int | None = None
    claimed_by_user_name: str | None = None


class InvoiceCodeBatchOut(BaseModel):
    """The codes just minted (also returned so a sheet can be printed at once)."""

    items: list[InvoiceCodeOut]
    created: int


class InvoiceCodeStats(BaseModel):
    """Lifecycle counts for one partner's code inventory."""

    issued: int = 0
    claimed: int = 0
    redeemed: int = 0
    revoked: int = 0
    total: int = 0