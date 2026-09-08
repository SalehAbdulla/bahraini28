"""Daily-usage-limit tests.

Rule: each volunteer may use a given business at most 3 times per *calendar
day*. The limit is independent per business and resets automatically at
midnight (the count is derived from transactions whose ``created_at`` is on
or after the start of today in the configured timezone).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Transaction
from tests.conftest import auth_headers, login, make_business, make_user


def submit(client, token, business_id, invoice):
    return client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={"business_id": business_id, "invoice_number": invoice},
    )


def setup_activated_user(client, db):
    user = make_user(
        db, email="limits@example.com", password="pass12345", must_change_password=False
    )
    token = login(client, "limits@example.com", "pass12345")
    return user, token


def test_three_uses_per_day_allowed(client, db):
    user, token = setup_activated_user(client, db)
    bz = make_business(db)

    for i in range(3):
        res = submit(client, token, bz.id, f"INV-{i}")
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["remaining_today"] == 2 - i
        assert body["reward_points_balance"] == i + 1

    db.refresh(user)
    assert user.reward_points == 3


def test_fourth_use_same_day_blocked(client, db):
    _, token = setup_activated_user(client, db)
    bz = make_business(db)

    for i in range(3):
        assert submit(client, token, bz.id, f"INV-{i}").status_code == 201

    res = submit(client, token, bz.id, "INV-3")
    assert res.status_code == 429
    assert res.json()["code"] == "daily_limit_exceeded"


def test_limit_is_independent_per_business(client, db):
    _, token = setup_activated_user(client, db)
    bz_a = make_business(db, name="Business A", cr="CR-A")
    bz_b = make_business(db, name="Business B", cr="CR-B")

    for i in range(3):
        assert submit(client, token, bz_a.id, f"AAA-{i}").status_code == 201
    # A is exhausted today, but B is still available.
    for i in range(3):
        assert submit(client, token, bz_b.id, f"BBB-{i}").status_code == 201
    assert submit(client, token, bz_b.id, "BBB-3").status_code == 429


def test_duplicate_invoice_rejected(client, db):
    _, token = setup_activated_user(client, db)
    bz = make_business(db)

    assert submit(client, token, bz.id, "SAME").status_code == 201
    res = submit(client, token, bz.id, "SAME")
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_invoice"


def test_previous_day_uses_do_not_count(client, db):
    """Automatic midnight reset: yesterday's uses don't consume today's quota."""
    user, token = setup_activated_user(client, db)
    bz = make_business(db)

    # Backdate three transactions to *yesterday* in the test timezone (UTC).
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    for i in range(3):
        db.add(
            Transaction(
                user_id=user.id,
                business_id=bz.id,
                invoice_number=f"OLD-{i}",
                reward_increment=1,
                created_at=yesterday.replace(hour=10, minute=0),
            )
        )
    db.commit()

    # Today's quota is still 3 (the old invoices don't count toward it).
    for i in range(3):
        res = submit(client, token, bz.id, f"NEW-{i}")
        assert res.status_code == 201, res.text
        assert res.json()["used_today"] == i + 1

    # And the 4th one is now blocked.
    assert submit(client, token, bz.id, "NEW-3").status_code == 429