"""Tier 2 tests: receipt proof + admin approval.

Covers the guarantees that make a reward *provable* rather than asserted:

1. a submission with no receipt is refused while ``REQUIRE_RECEIPT_REVIEW``;
2. a receipt-backed submission lands ``pending`` and credits **nothing**;
3. approving credits the reward once, stamps the reviewer, and writes a
   ``RewardAdjustment`` audit row;
4. rejecting never touches the balance and stores the reason for the volunteer;
5. a decided row cannot be decided again (409);
6. the same receipt *image* cannot back two invoices at one partner;
7. the daily caps still count ``pending`` rows (queueing must not bypass them);
8. the Tier-1 fallback (``REQUIRE_RECEIPT_REVIEW=False``) still credits
   instantly, so an un-onboarded deployment (and the Tier 1 suite) keeps
   working.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import RewardAdjustment, Transaction, User
from tests.conftest import admin_login, auth_headers, login, make_business, make_user

RECEIPT_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def submit(client, token, business_id, invoice, payload=RECEIPT_BYTES, extra=None):
    """Multipart submission — the shape the volunteer UI now posts."""
    files = None
    if payload is not None:
        files = {"receipt": ("receipt.png", payload, "image/png")}
    data = {"business_id": str(business_id), "invoice_number": invoice}
    data.update(extra or {})
    return client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        data=data,
        files=files,
    )


def user_token(client, db, email="review@example.com"):
    user = make_user(db, email=email, password="pass12345", must_change_password=False)
    return user, login(client, email, "pass12345")


def admin_headers(client):
    return auth_headers(admin_login(client))


# --- 1. the receipt is mandatory ------------------------------------------------


def test_submission_without_receipt_is_rejected(review_client, review_db):
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)

    res = submit(review_client, token, bz.id, "INV-NORCPT", payload=None)
    assert res.status_code == 400
    assert res.json()["code"] == "receipt_required"


def test_submission_rejects_unsupported_receipt_type(review_client, review_db):
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)

    res = review_client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        data={"business_id": str(bz.id), "invoice_number": "INV-TXT"},
        files={"receipt": ("notes.txt", b"not a receipt", "text/plain")},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "unsupported_file_type"


# --- 2. pending, with nothing credited ------------------------------------------


def test_submission_with_receipt_is_pending_and_credits_nothing(review_client, review_db):
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)

    res = submit(review_client, token, bz.id, "INV-0001")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["reward_points_balance"] == 0
    assert body["remaining_today"] == 2

    me = review_client.get("/api/v1/users/me", headers=auth_headers(token)).json()
    assert me["reward_points"] == 0  # nothing spendable yet
    assert me["pending_reward_points"] == 1

    # The admin queue exposes the receipt URL (served from /uploads).
    queue = review_client.get(
        "/api/v1/admin/transactions/review", headers=admin_headers(review_client)
    ).json()
    assert queue["total"] == 1
    item = queue["items"][0]
    assert item["status"] == "pending"
    assert item["invoice_number"] == "INV-0001"
    assert item["receipt_url"].startswith("/uploads/r")


# --- 3. approval credits once and audits ----------------------------------------


def test_approve_credits_reward_and_writes_audit_row(review_client, review_db):
    user, token = user_token(review_client, review_db)
    bz = make_business(review_db)
    tx_id = submit(review_client, token, bz.id, "INV-0002").json()["id"]

    res = review_client.post(
        f"/api/v1/admin/transactions/{tx_id}/approve", headers=admin_headers(review_client)
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "approved"
    assert body["reviewed_at"] is not None

    me = review_client.get("/api/v1/users/me", headers=auth_headers(token)).json()
    assert me["reward_points"] == 1
    assert me["pending_reward_points"] == 0

    review_db.expire_all()
    row = review_db.get(Transaction, tx_id)
    assert row.status == "approved"
    assert row.reviewed_by is not None  # traceable to an admin
    assert row.reviewed_at is not None

    audit = review_db.scalars(
        select(RewardAdjustment).where(RewardAdjustment.user_id == user.id)
    ).all()
    assert len(audit) == 1
    assert audit[0].delta == 1
    assert audit[0].reason == f"invoice approval #{tx_id}"
    assert audit[0].admin_id == row.reviewed_by


# --- 4. rejection never credits -------------------------------------------------


def test_reject_keeps_balance_and_stores_reason(review_client, review_db):
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)
    tx_id = submit(review_client, token, bz.id, "INV-0003").json()["id"]

    res = review_client.post(
        f"/api/v1/admin/transactions/{tx_id}/reject",
        headers=admin_headers(review_client),
        json={"reason": "Photo is too blurry to read"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Photo is too blurry to read"

    me = review_client.get("/api/v1/users/me", headers=auth_headers(token)).json()
    assert me["reward_points"] == 0
    assert me["pending_reward_points"] == 0

    # The volunteer is told why — on their *own* history only.
    history = review_client.get(
        "/api/v1/users/me/transactions", headers=auth_headers(token)
    ).json()
    assert history["items"][0]["rejection_reason"] == "Photo is too blurry to read"

    public = review_client.get(f"/api/v1/businesses/{bz.id}/transactions").json()
    assert public["items"][0]["status"] == "rejected"
    assert public["items"][0]["rejection_reason"] is None


# --- 5. a decision is final ----------------------------------------------------


def test_decided_submission_cannot_be_reviewed_again(review_client, review_db):
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)
    tx_id = submit(review_client, token, bz.id, "INV-0004").json()["id"]
    headers = admin_headers(review_client)

    assert review_client.post(
        f"/api/v1/admin/transactions/{tx_id}/approve", headers=headers
    ).status_code == 200

    second = review_client.post(
        f"/api/v1/admin/transactions/{tx_id}/approve", headers=headers
    )
    assert second.status_code == 409
    assert second.json()["code"] == "transaction_not_pending"

    # Rejecting an approved row is refused too — the reward stays intact.
    third = review_client.post(
        f"/api/v1/admin/transactions/{tx_id}/reject", headers=headers, json={}
    )
    assert third.status_code == 409
    me = review_client.get("/api/v1/users/me", headers=auth_headers(token)).json()
    assert me["reward_points"] == 1  # not double-credited, not rolled back


def test_reviewing_unknown_transaction_is_404(review_client, review_db):
    res = review_client.post(
        "/api/v1/admin/transactions/999999/approve", headers=admin_headers(review_client)
    )
    assert res.status_code == 404
    assert res.json()["code"] == "transaction_not_found"


# --- 6. one receipt image, one invoice -----------------------------------------


def test_same_receipt_image_cannot_back_two_invoices(review_client, review_db):
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)
    image = b"\x89PNG\r\n\x1a\n" + b"\x11" * 32

    assert submit(review_client, token, bz.id, "INV-IMG-1", payload=image).status_code == 201

    res = submit(review_client, token, bz.id, "INV-IMG-2", payload=image)
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_invoice"
    assert "receipt image" in res.json()["detail"]


# --- 7. the daily caps still count pending rows --------------------------------


def test_daily_cap_counts_pending_submissions(review_client, review_db):
    """Queueing must not bypass the per-business cap (test limit = 3)."""
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)

    for i in range(3):
        res = submit(review_client, token, bz.id, f"INV-CAP-{i}", payload=b"x" * 32 + bytes([i]))
        assert res.status_code == 201, res.text
        assert res.json()["status"] == "pending"

    blocked = submit(review_client, token, bz.id, "INV-CAP-3", payload=b"y" * 32)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "daily_limit_exceeded"


def test_rejected_submission_does_not_consume_the_daily_cap(review_client, review_db):
    """An honest mistake (blurry photo) must not cost the volunteer a slot."""
    _, token = user_token(review_client, review_db)
    bz = make_business(review_db)
    headers = admin_headers(review_client)

    ids = [
        submit(review_client, token, bz.id, f"INV-R-{i}", payload=bytes([i]) * 40).json()["id"]
        for i in range(3)
    ]
    assert submit(review_client, token, bz.id, "INV-R-3", payload=b"z" * 40).status_code == 429

    assert review_client.post(
        f"/api/v1/admin/transactions/{ids[0]}/reject", headers=headers, json={}
    ).status_code == 200

    # The freed slot can be used again.
    assert submit(review_client, token, bz.id, "INV-R-4", payload=b"w" * 40).status_code == 201


# --- 8. the Tier-1 fallback is unchanged ---------------------------------------


def test_tier1_fallback_credits_instantly_without_a_receipt(client, db):
    """With ``REQUIRE_RECEIPT_REVIEW=False`` the old behaviour is preserved."""
    assert client.app.state.settings.REQUIRE_RECEIPT_REVIEW is False
    make_user(db, email="fallback@example.com", password="pass12345", must_change_password=False)
    token = login(client, "fallback@example.com", "pass12345")
    bz = make_business(db)

    res = client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={"business_id": bz.id, "invoice_number": "INV-TIER1"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "approved"
    assert body["reward_points_balance"] == 1