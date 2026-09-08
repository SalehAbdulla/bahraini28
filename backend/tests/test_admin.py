"""Admin control-center tests: user CRUD, expiry override, reward adjustment,
password reset, analytics and the transaction ledger."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import (
    admin_login,
    auth_headers,
    login,
    make_business,
    make_user,
)


def admin_headers(client):
    return auth_headers(admin_login(client))


def test_admin_metrics(client, db):
    make_user(db, email="m1@example.com", password="pass12345", must_change_password=False)
    make_business(db)

    res = client.get("/api/v1/admin/metrics", headers=admin_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["total_users"] >= 1
    assert body["total_businesses"] >= 1


def test_admin_create_and_list_users(client, db):
    res = client.post(
        "/api/v1/admin/users",
        headers=admin_headers(client),
        json={
            "cpr": "2000000001",
            "email": "new.user@example.com",
            "name": "New User",
            "phone": "+973 1111",
            "password": "temporary1",
            "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            "reward_points": 5,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "new.user@example.com"
    assert body["reward_points"] == 5
    assert body["must_change_password"] is True

    res = client.get("/api/v1/admin/users", headers=admin_headers(client))
    assert res.status_code == 200
    assert res.json()["total"] >= 1


def test_admin_create_duplicate_cpr_conflict(client, db):
    make_user(db, cpr="3000000001", email="exists@example.com", password="pass12345")
    res = client.post(
        "/api/v1/admin/users",
        headers=admin_headers(client),
        json={
            "cpr": "3000000001",
            "email": "other@example.com",
            "name": "Other",
            "password": "temporary1",
            "expiry_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    )
    assert res.status_code == 409
    assert res.json()["code"] == "cpr_conflict"


def test_admin_expiry_override(client, db):
    user = make_user(db, email="expire@example.com", password="pass12345")
    new_expiry = datetime.now(timezone.utc) + timedelta(days=500)
    res = client.put(
        f"/api/v1/admin/users/{user.id}/expiry",
        headers=admin_headers(client),
        json={"expiry_date": new_expiry.isoformat()},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["expiry_date"].startswith(new_expiry.strftime("%Y-%m-%d"))


def test_admin_reward_adjustment(client, db):
    user = make_user(db, email="reward@example.com", password="pass12345", reward_points=10)
    res = client.put(
        f"/api/v1/admin/users/{user.id}/reward",
        headers=admin_headers(client),
        json={"delta": 5, "reason": "Volunteer recognition"},
    )
    assert res.status_code == 200
    assert res.json()["reward_points"] == 15

    res = client.put(
        f"/api/v1/admin/users/{user.id}/reward",
        headers=admin_headers(client),
        json={"delta": -20, "reason": "Correction"},
    )
    assert res.status_code == 200
    # never goes below zero
    assert res.json()["reward_points"] == 0


def test_admin_deactivate_invalidates_sessions(client, db):
    user = make_user(db, email="ban@example.com", password="pass12345", must_change_password=False)
    user_token = login(client, "ban@example.com", "pass12345")
    assert client.get("/api/v1/users/me", headers=auth_headers(user_token)).status_code == 200

    res = client.post(
        f"/api/v1/admin/users/{user.id}/deactivate",
        headers=admin_headers(client),
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # the user's sessions are killed and login is blocked
    assert client.get("/api/v1/users/me", headers=auth_headers(user_token)).status_code == 401
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "ban@example.com", "password": "pass12345"},
    )
    assert res.status_code == 403


def test_admin_reset_password_forces_change(client, db):
    user = make_user(db, email="reset@example.com", password="pass12345", must_change_password=False)
    res = client.post(
        f"/api/v1/admin/users/{user.id}/reset-password",
        headers=admin_headers(client),
        json={"new_password": "freshpass1"},
    )
    assert res.status_code == 200
    assert res.json()["must_change_password"] is True

    # old password gone, new one works and forces activation flow
    assert client.post(
        "/api/v1/auth/login",
        json={"identifier": "reset@example.com", "password": "pass12345"},
    ).status_code == 401
    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "reset@example.com", "password": "freshpass1"},
    )
    assert res.status_code == 200
    assert res.json()["must_change_password"] is True


def test_admin_user_analytics(client, db):
    user = make_user(db, email="analytics@example.com", password="pass12345", must_change_password=False)
    token = login(client, "analytics@example.com", "pass12345")
    bz = make_business(db, name="Fav Store", cr="CR-FAV")
    bz2 = make_business(db, name="Other Store", cr="CR-OTH")
    for inv in ("INV-A1", "INV-A2", "INV-B1"):
        bid = bz.id if inv.startswith("INV-A") else bz2.id
        res = client.post(
            "/api/v1/transactions",
            headers=auth_headers(token),
            json={"business_id": bid, "invoice_number": inv},
        )
        assert res.status_code == 201, res.text

    res = client.get(
        f"/api/v1/admin/users/{user.id}/analytics", headers=admin_headers(client)
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_transactions"] == 3
    assert body["most_frequented_business"]["business_name"] == "Fav Store"
    assert body["most_frequented_business"]["count"] == 2
    assert len(body["recent_transactions"]) == 3


def test_admin_transaction_ledger(client, db):
    user = make_user(db, email="ledger@example.com", password="pass12345", must_change_password=False)
    token = login(client, "ledger@example.com", "pass12345")
    bz1 = make_business(db, name="Ledger Store One", cr="CR-LED1")
    bz2 = make_business(db, name="Ledger Store Two", cr="CR-LED2")
    # Spread across two businesses to respect the 3/day/business limit.
    for i in range(3):
        assert client.post(
            "/api/v1/transactions",
            headers=auth_headers(token),
            json={"business_id": bz1.id, "invoice_number": f"LED1-{i}"},
        ).status_code == 201
    for i in range(2):
        assert client.post(
            "/api/v1/transactions",
            headers=auth_headers(token),
            json={"business_id": bz2.id, "invoice_number": f"LED2-{i}"},
        ).status_code == 201

    res = client.get("/api/v1/admin/transactions", headers=admin_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5

    res = client.get(
        "/api/v1/admin/transactions?search=LED1-2", headers=admin_headers(client)
    )
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_user_token_cannot_access_admin(client, db):
    make_user(db, email="notadmin@example.com", password="pass12345", must_change_password=False)
    user_token = login(client, "notadmin@example.com", "pass12345")
    res = client.get("/api/v1/admin/metrics", headers=auth_headers(user_token))
    assert res.status_code == 401