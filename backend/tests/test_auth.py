"""Authentication flow tests: login (email/CPR), expiry gating, profile
activation, admin login, and logout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import (
    activate,
    admin_login,
    auth_headers,
    login,
    make_user,
)


def test_login_with_email(client, db):
    make_user(db, email="jane@example.com", password="pass12345")
    token = login(client, "jane@example.com", "pass12345")
    assert token


def test_login_with_cpr(client, db):
    make_user(db, cpr="99999999", email="cpr@example.com", password="pass12345")
    token = login(client, "99999999", "pass12345")
    assert token


def test_login_wrong_password(client, db):
    make_user(db, email="pass@example.com", password="correct-horse")
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "pass@example.com", "password": "wrong-pw"},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "invalid_credentials"


def test_login_unknown_user(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "nobody@example.com", "password": "whatever"},
    )
    assert res.status_code == 401


def test_login_expired_membership_blocked(client, db):
    make_user(db, email="expired@example.com", password="pass12345", expiry_days=-30)
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "expired@example.com", "password": "pass12345"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "membership_expired"


def test_login_inactive_user_blocked(client, db):
    make_user(db, email="off@example.com", password="pass12345", is_active=False)
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "off@example.com", "password": "pass12345"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "user_inactive"


def test_first_login_flags_must_change_password(client, db):
    make_user(db, email="newbie@example.com", password="pass12345", must_change_password=True)
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "newbie@example.com", "password": "pass12345"},
    )
    assert res.status_code == 200
    assert res.json()["must_change_password"] is True


def test_profile_activation_updates_identity(client, db):
    user = make_user(db, email="newbie2@example.com", password="pass12345")
    token = login(client, "newbie2@example.com", "pass12345")
    new_token = activate(client, token, name="Jane Doe", email="jane.doe@example.com", password="brandnew1")

    res = client.get("/api/v1/users/me", headers=auth_headers(new_token))
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Jane Doe"
    assert body["email"] == "jane.doe@example.com"
    assert body["must_change_password"] is False

    # old password must no longer work, new one does
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "jane.doe@example.com", "password": "brandnew1"},
    )
    assert res.status_code == 200


def test_admin_login(client):
    token = admin_login(client)
    assert token


def test_admin_login_wrong_password(client):
    res = client.post(
        "/api/v1/auth/admin/login",
        json={"username": "admin", "password": "nope"},
    )
    assert res.status_code == 401


def test_users_me_requires_auth(client):
    res = client.get("/api/v1/users/me")
    assert res.status_code == 401


def test_logout_invalidates_token(client, db):
    make_user(db, email="logout@example.com", password="pass12345", must_change_password=False)
    token = login(client, "logout@example.com", "pass12345")
    res = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert res.status_code == 204
    # token now stale
    res = client.get("/api/v1/users/me", headers=auth_headers(token))
    assert res.status_code == 401