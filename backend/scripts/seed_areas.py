"""Import the real Bahrain areas into the database.

Reads ``backend/data/bahrain_areas.csv`` (``governorate,area``) — derived from
the organization's official Bahrain address list — and upserts the distinct
area names into the ``areas`` table.

Idempotent: names are matched case-insensitively and existing areas are left
untouched, so the script can be re-run safely after a data refresh.

Usage (from the backend/ directory):
    cd backend
    PYTHONPATH=. ../.venv/bin/python scripts/seed_areas.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Area

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "bahrain_areas.csv"


def load_area_names(path: Path = DATA_FILE) -> list[str]:
    """Return the distinct area names from the CSV, preserving first-seen order."""
    names: list[str] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("area") or "").strip()
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                names.append(name)
    return names


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    names = load_area_names()
    created = 0
    with SessionLocal() as db:
        existing = {area.name.casefold() for area in db.scalars(select(Area)).all()}
        for name in names:
            if name.casefold() in existing:
                continue
            db.add(Area(name=name))
            existing.add(name.casefold())
            created += 1
        db.commit()

    skipped = len(names) - created
    print(
        f"Areas imported: {created} created, {skipped} already present "
        f"({len(names)} distinct names in {DATA_FILE.name})."
    )


if __name__ == "__main__":
    seed()
