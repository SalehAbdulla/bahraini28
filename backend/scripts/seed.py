"""Seed the database with demo data for local development.

Usage (from the backend/ directory):
    cd backend
    PYTHONPATH=. ../.venv/bin/python scripts/seed.py

Requires ``SEED_DEFAULT_ADMIN`` (the app already creates the initial admin on
startup when enabled); this script adds sample categories, areas, businesses
and a demo volunteer account.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models import Area, Business, BusinessArea, Category, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tznow(days: int = 0) -> datetime:
    return _now() + timedelta(days=days)


def seed() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        # --- categories ------------------------------------------------------
        categories = [
            ("Restaurants & Cafes", "restaurants"),
            ("Health & Beauty", "health-beauty"),
            ("Retail & Shopping", "retail"),
            ("Education & Books", "education"),
            ("Sports & Fitness", "sports-fitness"),
        ]
        cat_objs: dict[str, Category] = {}
        for name, slug in categories:
            cat = db.scalar(select(Category).where(Category.slug == slug))
            if cat is None:
                cat = Category(name=name, slug=slug, description=f"{name} partners")
                db.add(cat)
                db.flush()
            cat_objs[slug] = cat

        # --- areas -------------------------------------------------------------
        areas = ["Manama", "Riffa", "Muharraq", "Seef", "Juffair", "Isa Town"]
        area_objs: list[Area] = []
        for name in areas:
            area = db.scalar(select(Area).where(Area.name == name))
            if area is None:
                area = Area(name=name)
                db.add(area)
                db.flush()
            area_objs.append(area)

        # --- businesses ----------------------------------------------------------
        businesses = [
            {
                "name": "Café Bahraini",
                "cr": "CR-1001",
                "category": "restaurants",
                "discount": 20,
                "desc": "Specialty coffee and traditional pastries with a member discount.",
                "areas": [(0, "Café Bahraini – Seef"), (5, "Café Bahraini – Isa Town")],
            },
            {
                "name": "Souk Boutique",
                "cr": "CR-1002",
                "category": "retail",
                "discount": 15,
                "desc": "Local fashion and giftware.",
                "areas": [(0, "Souk Boutique – Manama")],
            },
            {
                "name": "Wellness Center",
                "cr": "CR-1003",
                "category": "health-beauty",
                "discount": 25,
                "desc": "Massage, skincare and wellness services.",
                "areas": [(0, "Wellness – Juffair")],
            },
            {
                "name": "Books & Coffee House",
                "cr": "CR-1004",
                "category": "education",
                "discount": 10,
                "desc": "Books, stationery and a reading lounge.",
                "areas": [(0, "Books & Coffee – Riffa")],
            },
            {
                "name": "FitLab Gym",
                "cr": "CR-1005",
                "category": "sports-fitness",
                "discount": 30,
                "desc": "Gym memberships and personal training.",
                "areas": [(0, "FitLab – Muharraq"), (3, "FitLab – Seef")],
            },
        ]
        bz_objs: list[Business] = []
        for spec in businesses:
            business = db.scalar(
                select(Business).where(Business.commercial_registration == spec["cr"])
            )
            if business is None:
                business = Business(
                    name=spec["name"],
                    commercial_registration=spec["cr"],
                    category_id=cat_objs[spec["category"]].id,
                    discount_percentage=spec["discount"],
                    description=spec["desc"],
                    is_active=True,
                    expiry_date=_tznow(365),
                )
                db.add(business)
                db.flush()
                for area_idx, branch_name in spec["areas"]:
                    db.add(
                        BusinessArea(
                            business_id=business.id,
                            area_id=area_objs[area_idx].id,
                            branch_name=branch_name,
                        )
                    )
            bz_objs.append(business)

        # --- demo volunteer ------------------------------------------------------
        if db.scalar(select(User).where(User.cpr == "100000000000")):
            print("Demo user already exists; skipping.")
        else:
            db.add(
                User(
                    cpr="100000000000",
                    email="volunteer@example.com",
                    name="Demo Volunteer",
                    phone="+973 3000 0000",
                    password_hash=hash_password("volunteer123"),
                    expiry_date=_tznow(90),
                    is_active=True,
                    must_change_password=True,
                    reward_points=0,
                )
            )
        db.commit()

    print("Seed complete. Demo login:")
    print("  User : volunteer@example.com / volunteer123")
    print("  Admin: admin / admin123")


if __name__ == "__main__":
    seed()