"""Single-session enforcement tests.

Volunteer logins must invalidate prior tokens (``token_version`` roll). Admin
sessions are exempt by design.
"""
from __future__ import annotations

from tests.conftest import admin_login, auth_headers, login, make_user


def test_new_login_invalidates_old_token(client, db):
    make_user(db, email="sessions@example.com", password="pass12345", must_change_password=False)

    token1 = login(client, "sessions@example.com", "pass12345")
    assert client.get("/api/v1/users/me", headers=auth_headers(token1)).status_code == 200

    token2 = login(client, "sessions@example.com", "pass12345")
    assert token2 != token1

    # token1 has been invalidated by the newer login
    res = client.get("/api/v1/users/me", headers=auth_headers(token1))
    assert res.status_code == 401
    assert res.json()["code"] == "session_invalidated"

    # token2 still valid
    assert client.get("/api/v1/users/me", headers=auth_headers(token2)).status_code == 200


def test_multiple_sessions_only_last_is_valid(client, db):
    make_user(db, email="multi@example.com", password="pass12345", must_change_password=False)

    t1 = login(client, "multi@example.com", "pass12345")
    t2 = login(client, "multi@example.com", "pass12345")
    t3 = login(client, "multi@example.com", "pass12345")

    assert client.get("/api/v1/users/me", headers=auth_headers(t1)).status_code == 401
    assert client.get("/api/v1/users/me", headers=auth_headers(t2)).status_code == 401
    assert client.get("/api/v1/users/me", headers=auth_headers(t3)).status_code == 200


def test_admin_is_exempt_from_single_session(client):
    # Admins can hold multiple simultaneous sessions: old admin tokens remain
    # valid after a new admin login (no token_version roll for admins).
    t1 = admin_login(client)
    t2 = admin_login(client)
    assert t1 != t2
    r1 = client.get("/api/v1/admin/metrics", headers=auth_headers(t1))
    r2 = client.get("/api/v1/admin/metrics", headers=auth_headers(t2))
    assert r1.status_code == 200
    assert r2.status_code == 200