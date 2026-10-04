"""Seed the database with demo data for local development.

Usage (from the backend/ directory):
    cd backend
    PYTHONPATH=. ../.venv/bin/python scripts/seed.py

Requires ``SEED_DEFAULT_ADMIN`` (the app already creates the initial admin on
startup when enabled); this script adds sample categories, areas, businesses,
a demo volunteer account, and a batch of single-use receipt codes for the
partner that requires them (anti-fraud Tier 3) — so the code-required flow is
visible on a fresh demo run.

Every step is idempotent: a row matched on its natural key is left untouched, and
the demo code batch is only minted while the partner has none.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models import Area, Business, BusinessArea, Category, InvoiceCode, User
from app.services.invoice_codes import create_batch


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
            {
                # Anti-fraud Tier 3: this partner prints a single-use code on each
                # receipt, so a submission must quote one (minted below). Named to
                # sort *last* in the directory, so a code-required partner never
                # becomes the "first card" that tooling (e2e) clicks by default.
                "name": "Zaytoun Grocers",
                "cr": "CR-1006",
                "category": "retail",
                "discount": 12,
                "desc": "Fresh produce and pantry staples; prints a single-use receipt code.",
                "codes_required": True,
                "areas": [(1, "Zaytoun – Riffa"), (4, "Zaytoun – Juffair")],
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
                    # Tier 3 opt-in — absent from every partner but Zaytoun.
                    codes_required=spec.get("codes_required", False),
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

        # --- demo single-use codes (anti-fraud Tier 3) ---------------------------
        # Minted once: re-running the seed must not stack up codes. Attribution is
        # left null because this runs *before* the app creates the bootstrap admin
        # (see run.sh and e2e/conftest.py).
        code_partner = next((b for b in bz_objs if b.codes_required), None)
        if code_partner is not None:
            already = db.scalar(
                select(func.count(InvoiceCode.id)).where(
                    InvoiceCode.business_id == code_partner.id
                )
            )
            if already:
                print(
                    f"{code_partner.name}: {already} demo code(s) already exist; skipping."
                )
            else:
                codes = create_batch(
                    db,
                    business_id=code_partner.id,
                    count=5,
                    batch="demo-sheet",
                    admin_id=None,
                )
                print(f"Demo single-use codes for {code_partner.name}:")
                for code in codes:
                    print(f"  {code.code}")

    print("Seed complete. Demo login:")
    print("  User : volunteer@example.com / volunteer123")
    print("  Admin: admin / admin123")
    print("  Tier 3: Zaytoun Grocers requires a receipt code — issue and print")
    print("          codes at /admin/businesses/<id>/codes")


if __name__ == "__main__":
    seed()