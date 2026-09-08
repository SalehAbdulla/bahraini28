"""Transaction (invoice submission) tests: reward increments, business
status guards, and personal/public history endpoints."""
from __future__ import annotations

from tests.conftest import auth_headers, login, make_business, make_user


def submit(client, token, business_id, invoice):
    return client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={"business_id": business_id, "invoice_number": invoice},
    )


def active_user_token(client, db, email="tx@example.com"):
    make_user(db, email=email, password="pass12345", must_change_password=False)
    return login(client, email, "pass12345")


def test_submit_invoice_increments_reward_points(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)

    res = submit(client, token, bz.id, "INV-0001")
    assert res.status_code == 201
    body = res.json()
    assert body["reward_increment"] == 1
    assert body["reward_points_balance"] == 1
    assert body["business_name"] == bz.name


def test_submit_inactive_business_blocked(client, db):
    token = active_user_token(client, db)
    bz = make_business(db, is_active=False)

    res = submit(client, token, bz.id, "INV-1")
    assert res.status_code == 403
    assert res.json()["code"] == "business_inactive"


def test_submit_expired_business_blocked(client, db):
    token = active_user_token(client, db)
    bz = make_business(db, expiry_days=-5)

    res = submit(client, token, bz.id, "INV-1")
    assert res.status_code == 403
    assert res.json()["code"] == "business_expired"


def test_submit_unknown_business_not_found(client, db):
    token = active_user_token(client, db)
    res = submit(client, token, 999_999, "INV-1")
    assert res.status_code == 404


def test_invoice_number_trimmed(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)

    res = submit(client, token, bz.id, "  INV-ABC  ")
    assert res.status_code == 201
    assert res.json()["invoice_number"] == "INV-ABC"


def test_personal_transaction_history(client, db):
    token = active_user_token(client, db)
    bz1 = make_business(db, name="Biz One", cr="CR-O1")
    bz2 = make_business(db, name="Biz Two", cr="CR-O2")

    submit(client, token, bz1.id, "INV-1")
    submit(client, token, bz2.id, "INV-2")

    res = client.get("/api/v1/users/me/transactions", headers=auth_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    names = {t["business_name"] for t in body["items"]}
    assert names == {"Biz One", "Biz Two"}


def test_public_business_transaction_history(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)
    submit(client, token, bz.id, "INV-PUB-1")

    # Public (no auth) history for the business is paginated and readable.
    res = client.get(f"/api/v1/businesses/{bz.id}/transactions")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["business_name"] == bz.name