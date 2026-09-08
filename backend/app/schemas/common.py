"""Shared schemas: pagination shapes and common fields."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Paginated response envelope used across list endpoints."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(12, ge=1, le=100)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)