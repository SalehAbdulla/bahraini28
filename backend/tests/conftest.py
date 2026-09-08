"""Shared fixtures: an app wired to an in-memory SQLite database.

Each test gets a fresh in-memory engine (``StaticPool`` shares one connection
so all sessions see the same data), with tables created automatically.
"""
from __future__ import annotations

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


def make_test_settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite:///:memory:",
        DB_ECHO=False,
        SECRET_KEY=TEST_SECRET,
        JWT_ALGORITHM="HS256",
        DEFAULT_TIMEZONE=TEST_TZ,
        DAILY_LIMIT_PER_BUSINESS=TEST_LIMIT,
        SEED_DEFAULT_ADMIN=True,
        ADMIN_INITIAL_USERNAME="admin",
        ADMIN_INITIAL_PASSWORD="admin123",
        ADMIN_INITIAL_NAME="Test Admin",
        CORS_ORIGINS=["http://localhost:5173"],
    )


@pytest.fixture
def app():
    settings = make_test_settings()
    application = create_app(settings)
    yield application


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


def make_business(db, *, name="Test Business", cr="CR-TEST-1", discount=20,
                  category=None, area=None, is_active=True, expiry_days=365) -> Business:
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
        is_active=is_active,
        expiry_date=datetime.now(timezone.utc) + timedelta(days=expiry_days),
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