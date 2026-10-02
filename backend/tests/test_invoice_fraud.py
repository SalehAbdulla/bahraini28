"""Tests for the Tier 1 anti-fraud gates on invoice submission.

Covers the three holes that let a volunteer credit themselves with no real
purchase:

1. ``invoice_format`` — junk like ``"!"`` or blank-ish values are rejected.
2. ``global duplicate`` — an invoice can be credited at a partner only once,
   *by anyone* (not just by the same user).
3. ``total daily cap`` — a single account cannot farm rewards across every
   partner in the directory in one day.
"""
from __future__ import annotations

from app.core.errors import TotalDailyLimitExceededError
from tests.conftest import auth_headers, login, make_business, make_user


def submit(client, token, business_id, invoice):
    return client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={"business_id": business_id, "invoice_number": invoice},
    )


def active_user_token(client, db, email="fraud@example.com"):
    # Distinct CPR per user: the column is unique, and some tests create two.
    cpr = f"{abs(hash(email)) % 10**12:012d}"
    make_user(
        db,
        cpr=cpr,
        email=email,
        password="pass12345",
        must_change_password=False,
    )
    return login(client, email, "pass12345")


# --- 1. invoice format gate ----------------------------------------------------


def test_junk_invoice_number_rejected(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)

    res = submit(client, token, bz.id, "!!!")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_invoice_format"


def test_invoice_number_with_spaces_rejected(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)

    res = submit(client, token, bz.id, "AB 12")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_invoice_format"


def test_per_business_pattern_enforced(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)
    bz.invoice_pattern = r"B28-\d{5}"  # partner-specific format
    db.commit()

    assert submit(client, token, bz.id, "B28-12345").status_code == 201
    bad = submit(client, token, bz.id, "INV-99999")
    assert bad.status_code == 400
    assert bad.json()["code"] == "invalid_invoice_format"


# --- 2. global duplicate guard -------------------------------------------------


def test_invoice_cannot_be_shared_between_users(client, db):
    """The same receipt must not credit two different volunteers."""
    token_a = active_user_token(client, db, email="first@example.com")
    token_b = active_user_token(client, db, email="second@example.com")
    bz = make_business(db)

    assert submit(client, token_a, bz.id, "RECEIPT-1").status_code == 201
    res = submit(client, token_b, bz.id, "RECEIPT-1")
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_invoice"


def test_duplicate_guard_is_case_insensitive(client, db):
    token = active_user_token(client, db)
    bz = make_business(db)

    assert submit(client, token, bz.id, "inv-77").status_code == 201
    assert submit(client, token, bz.id, "INV-77").status_code == 409


# --- 3. total daily cap across all partners ------------------------------------


def test_total_daily_limit_blocks_directory_farming(client, db, monkeypatch):
    """With the total cap at 4, a 5th credit anywhere is refused."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "DAILY_LIMIT_TOTAL", 4, raising=False)
    monkeypatch.setattr(TotalDailyLimitExceededError, "remaining", 0, raising=False)

    token = active_user_token(client, db)
    businesses = [make_business(db, name=f"Partner {i}") for i in range(5)]

    for i in range(4):
        res = submit(client, token, businesses[i].id, f"INV-{i:04d}")
        assert res.status_code == 201, res.text
        assert res.json()["remaining_today_total"] == 3 - i

    # 5th credit (a different partner) is refused by the *total* cap.
    res = submit(client, token, businesses[4].id, "INV-9999")
    assert res.status_code == 429
    assert res.json()["code"] == "total_daily_limit_exceeded"