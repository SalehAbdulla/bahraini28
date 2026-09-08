"""Geographic areas and the business↔area association (multi-branch support)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import TZDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Area(Base):
    """A geographic area (e.g. Manama, Riffa, Muharraq...)."""
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=_utcnow, nullable=False
    )

    business_links: Mapped[list["BusinessArea"]] = relationship(  # noqa: F821
        back_populates="area", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Area id={self.id} name={self.name!r}>"


class BusinessArea(Base):
    """Association between a Business and an Area — one row per branch.

    A business with three branches across two areas has three rows, each with
    optional branch-level contact details.
    """
    __tablename__ = "business_areas"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "area_id", "branch_name",
            name="uq_business_area_branch",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), index=True)
    branch_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="areas")  # noqa: F821
    area: Mapped["Area"] = relationship(back_populates="business_links")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BusinessArea id={self.id} business={self.business_id} "
            f"area={self.area_id} branch={self.branch_name!r}>"
        )