"""Shared fixtures: an app wired to an in-memory SQLite database.

Each test gets a fresh in-memory engine (``StaticPool`` shares one connection
so all sessions see the same data), with tables created automatically.
"""
from __future__ import annotations

import os
import tempfile
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.base import Base
from app.core.security import hash_password
from app.main import create_app
from app.models import Admin, Area, Business, BusinessArea, Category, User

TEST_TZ = "UTC"
TEST_LIMIT = 3
TEST_SECRET = "test-secret-key"
# The Tier 1 daily-limit tests use a small per-business cap; keep the total
# ceiling and the fraud threshold high so they never interfere with tests that
# only mean to exercise the per-business rule.
TEST_TOTAL_LIMIT = 1000
TEST_FRAUD_THRESHOLD = 1000

# Logo-upload tests write real files; keep them out of the repo tree.
TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="bahraini28-test-uploads-")


def make_test_settings(*, require_receipt_review: bool = False) -> Settings:
    # The suite runs against an in-memory SQLite database by default. Set the
    # TEST_DATABASE_URL environment variable to re-run the exact same suite
    # against a real PostgreSQL instance (used by CI / repeatable checks).
    #
    # ``require_receipt_review`` defaults to False so the historical Tier 1
    # tests (which submit a JSON invoice and assert an instant balance) keep
    # passing; the Tier 2 tests opt in explicitly.
    database_url = os.environ.get("TEST_DATABASE_URL") or "sqlite:///:memory:"
    return Settings(
        DATABASE_URL=database_url,
        DB_ECHO=False,
        SECRET_KEY=TEST_SECRET,
        JWT_ALGORITHM="HS256",
        DEFAULT_TIMEZONE=TEST_TZ,
        DAILY_LIMIT_PER_BUSINESS=TEST_LIMIT,
        DAILY_LIMIT_TOTAL=TEST_TOTAL_LIMIT,
        FRAUD_DISTINCT_BUSINESSES_PER_DAY=TEST_FRAUD_THRESHOLD,
        REQUIRE_RECEIPT_REVIEW=require_receipt_review,
        SEED_DEFAULT_ADMIN=True,
        ADMIN_INITIAL_USERNAME="admin",
        ADMIN_INITIAL_PASSWORD="admin123",
        ADMIN_INITIAL_NAME="Test Admin",
        CORS_ORIGINS=["http://localhost:5173"],
        UPLOAD_DIR=TEST_UPLOAD_DIR,
    )


@pytest.fixture
def app():
    settings = make_test_settings()
    application = create_app(settings)
    yield application
    # Dispose the engine so pooled connections are returned on Postgres;
    # otherwise every test leaks its engine pool and CI servers with a
    # small max_connections can run out.
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    engine = app.state.engine
    session_factory = app.state.SessionLocal
    session = session_factory()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# --- Tier 2 fixtures (REQUIRE_RECEIPT_REVIEW=True) ---------------------------
# A separate app/engine so the receipt-review suite exercises the real default
# without changing the Tier-1 behaviour every other test module relies on.


@pytest.fixture
def review_app():
    settings = make_test_settings(require_receipt_review=True)
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def review_client(review_app) -> Generator[TestClient, None, None]:
    with TestClient(review_app) as c:
        yield c


@pytest.fixture
def review_db(review_app):
    engine = review_app.state.engine
    session = review_app.state.SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)
PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)


def make_user(db, *, cpr="100000000001", email="user@example.com", password="userpass123",
              name="Test Volunteer", expiry_days=365, must_change_password=True,
              reward_points=0, is_active=True) -> User:
    user = User(
        cpr=cpr,
        email=email,
        name=name,
        password_hash=hash_password(password),
        expiry_date=datetime.now(timezone.utc) + timedelta(days=expiry_days),
        must_change_password=must_change_password,
        reward_points=reward_points,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_business(db, *, name="Test Business", cr=None, discount=20,
                  category=None, area=None, is_active=True, expiry_days=365,
                  codes_required=False, discount_label=None) -> Business:
    # Default to a unique CR so additional businesses in one test never collide
    # with the unique commercial-registration constraint.
    if cr is None:
        cr = f"CR-{_uuid.uuid4().hex[:10]}"
    if category is None:
        category = db.scalar(select(Category).where(Category.slug == "test-cat"))
        if category is None:
            category = Category(name="Test Cat", slug="test-cat")
            db.add(category)
            db.flush()
    business = Business(
        name=name,
        commercial_registration=cr,
        category_id=category.id,
        discount_percentage=discount,
        discount_label=discount_label,
        is_active=is_active,
        expiry_date=datetime.now(timezone.utc) + timedelta(days=expiry_days),
        # Tier 3 opt-in: the partner prints single-use codes on its receipts.
        codes_required=codes_required,
    )
    db.add(business)
    db.flush()
    if area is not None:
        db.add(BusinessArea(business_id=business.id, area_id=area.id, branch_name=f"{name} branch"))
    db.commit()
    db.refresh(business)
    return business


def make_area(db, name="Manama") -> Area:
    area = Area(name=name)
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


def login(client, identifier, password) -> str:
    res = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_login(client, username="admin", password="admin123") -> str:
    res = client.post("/api/v1/auth/admin/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def activate(client, token, name="Real Name", email="activated@example.com", password="newpass123") -> str:
    res = client.post(
        "/api/v1/auth/activate-profile",
        headers=auth_headers(token),
        json={"name": name, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]