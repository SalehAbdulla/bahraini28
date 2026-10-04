"""Tier 3 tests: single-use merchant receipt codes.

Covers the control that makes a fabricated invoice *impossible* for a partner who
opts in — a submission must quote a code the admin issued to that partner:

1. an admin mints a batch; every code is ``B28-XXXX-XXXX``, ``issued``, and unique;
2. listing + stats report the inventory; revoking cancels an unclaimed code;
3. a ``codes_required`` partner refuses a submission with no code (400);
4. an unknown code, or one issued to a *different* partner, is refused (400);
5. a valid code is claimed on submission (the reward still waits for review);
6. approving redeems the code; rejecting returns it to the pool;
7. the same code cannot back two live submissions (409);
8. the Tier-1 fallback redeems a code instantly, since nothing is reviewed.
"""
from __future__ import annotations

from app.models import InvoiceCode
from tests.conftest import admin_login, auth_headers, login, make_business, make_user

RECEIPT_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def submit(client, token, business_id, invoice, payload=RECEIPT_BYTES, code=None):
    """Multipart submission — the shape the volunteer UI posts."""
    files = None
    if payload is not None:
        files = {"receipt": ("receipt.png", payload, "image/png")}
    data = {"business_id": str(business_id), "invoice_number": invoice}
    if code is not None:
        data["code"] = code
    return client.post(
        "/api/v1/transactions", headers=auth_headers(token), data=data, files=files
    )


def user_token(client, db, email="codes@example.com"):
    make_user(db, email=email, password="pass12345", must_change_password=False)
    return login(client, email, "pass12345")


def admin_headers(client):
    return auth_headers(admin_login(client))


def generate(client, headers, business_id, count=1, batch=None):
    """Mint a batch and return the created code rows (as JSON)."""
    body = {"count": count}
    if batch is not None:
        body["batch"] = batch
    res = client.post(
        f"/api/v1/admin/businesses/{business_id}/codes", headers=headers, json=body
    )
    assert res.status_code == 201, res.text
    return res.json()


def stats(client, headers, business_id):
    res = client.get(
        f"/api/v1/admin/businesses/{business_id}/codes/stats", headers=headers
    )
    assert res.status_code == 200, res.text
    return res.json()


def code_status(db, code_value):
    db.expire_all()
    row = db.query(InvoiceCode).filter(InvoiceCode.code == code_value).one()
    return row.status


# --- 1 & 2. issuing a batch, listing it, and revoking ---------------------------


def test_admin_can_generate_a_batch_of_unique_codes(review_client, review_db):
    bz = make_business(review_db)
    batch = generate(review_client, admin_headers(review_client), bz.id, count=5, batch="sheet-1")

    assert batch["created"] == 5
    codes = [item["code"] for item in batch["items"]]
    assert len(set(codes)) == 5  # globally unique
    for item in batch["items"]:
        assert item["code"].startswith("B28-")
        assert item["status"] == "issued"
        assert item["batch"] == "sheet-1"


def test_code_inventory_list_and_stats(review_client, review_db):
    bz = make_business(review_db)
    headers = admin_headers(review_client)
    generate(review_client, headers, bz.id, count=3)

    listing = review_client.get(
        f"/api/v1/admin/businesses/{bz.id}/codes", headers=headers
    ).json()
    assert listing["total"] == 3
    assert len(listing["items"]) == 3

    assert stats(review_client, headers, bz.id) == {
        "issued": 3,
        "claimed": 0,
        "redeemed": 0,
        "revoked": 0,
        "total": 3,
    }

    # The status filter must narrow the *items*, not only the count.
    redeemed = review_client.get(
        f"/api/v1/admin/businesses/{bz.id}/codes?status=redeemed", headers=headers
    ).json()
    assert redeemed["total"] == 0
    assert redeemed["items"] == []

    available = review_client.get(
        f"/api/v1/admin/businesses/{bz.id}/codes?status=issued", headers=headers
    ).json()
    assert available["total"] == 3
    assert len(available["items"]) == 3
    assert {c["status"] for c in available["items"]} == {"issued"}


def test_revoke_cancels_an_unclaimed_code(review_client, review_db):
    bz = make_business(review_db)
    headers = admin_headers(review_client)
    code_id = generate(review_client, headers, bz.id, count=1)["items"][0]["id"]

    res = review_client.delete(f"/api/v1/admin/codes/{code_id}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "revoked"
    assert stats(review_client, headers, bz.id)["revoked"] == 1


def test_codes_are_scoped_to_their_partner(review_client, review_db):
    first = make_business(review_db, name="First")
    second = make_business(review_db, name="Second")
    headers = admin_headers(review_client)
    code = generate(review_client, headers, first.id, count=1)["items"][0]["code"]

    # A code issued to `first` is not valid at `second`.
    token = user_token(review_client, review_db)
    res = submit(review_client, token, second.id, "INV-SCOPE", payload=b"a" * 40, code=code)
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_invoice_code"


# --- 3. a code-printing partner refuses a submission without a code -------------


def test_codes_required_partner_rejects_a_missing_code(review_client, review_db):
    bz = make_business(review_db, codes_required=True)
    token = user_token(review_client, review_db)

    res = submit(review_client, token, bz.id, "INV-NOCODE", payload=b"b" * 40)
    assert res.status_code == 400
    assert res.json()["code"] == "invoice_code_required"


def test_unknown_code_is_rejected(review_client, review_db):
    bz = make_business(review_db, codes_required=True)
    token = user_token(review_client, review_db)

    res = submit(review_client, token, bz.id, "INV-BOGUS", payload=b"c" * 40, code="B28-XXXX-XXXX")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_invoice_code"


# --- 5 & 6. claim on submit, redeem on approve, release on reject ---------------


def test_valid_code_is_claimed_and_reward_waits_for_review(review_client, review_db):
    bz = make_business(review_db, codes_required=True)
    headers = admin_headers(review_client)
    code = generate(review_client, headers, bz.id, count=1)["items"][0]["code"]
    token = user_token(review_client, review_db)

    res = submit(review_client, token, bz.id, "INV-CLAIM", payload=b"d" * 40, code=code)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["code"] == code
    # Nothing is credited yet, but the code is now held by the submission.
    assert body["reward_points_balance"] == 0
    assert code_status(review_db, code) == "claimed"
    assert stats(review_client, headers, bz.id)["claimed"] == 1


def test_approving_redeems_the_code(review_client, review_db):
    bz = make_business(review_db, codes_required=True)
    headers = admin_headers(review_client)
    code = generate(review_client, headers, bz.id, count=1)["items"][0]["code"]
    token = user_token(review_client, review_db)

    tx = submit(review_client, token, bz.id, "INV-APPROVE", payload=b"e" * 40, code=code).json()
    res = review_client.post(
        f"/api/v1/admin/transactions/{tx['id']}/approve", headers=headers
    )
    assert res.status_code == 200, res.text
    assert code_status(review_db, code) == "redeemed"
    assert stats(review_client, headers, bz.id)["redeemed"] == 1

    me = review_client.get("/api/v1/users/me", headers=auth_headers(token)).json()
    assert me["reward_points"] == 1


def test_rejecting_releases_the_code_for_reuse(review_client, review_db):
    bz = make_business(review_db, codes_required=True)
    headers = admin_headers(review_client)
    code = generate(review_client, headers, bz.id, count=1)["items"][0]["code"]
    token = user_token(review_client, review_db)

    tx = submit(review_client, token, bz.id, "INV-REJECT", payload=b"f" * 40, code=code).json()
    review_client.post(
        f"/api/v1/admin/transactions/{tx['id']}/reject",
        headers=headers,
        json={"reason": "Receipt too blurry"},
    )
    # The volunteer keeps the physical receipt, so the code is available again.
    assert code_status(review_db, code) == "issued"

    again = submit(review_client, token, bz.id, "INV-REJECT-2", payload=b"g" * 40, code=code)
    assert again.status_code == 201, again.text


# --- 7. one code, one live submission ------------------------------------------


def test_same_code_cannot_back_two_submissions(review_client, review_db):
    bz = make_business(review_db, codes_required=True)
    headers = admin_headers(review_client)
    code = generate(review_client, headers, bz.id, count=1)["items"][0]["code"]
    token = user_token(review_client, review_db)

    assert submit(review_client, token, bz.id, "INV-ONE", payload=b"h" * 40, code=code).status_code == 201

    # A second (even honest) submission with the same code is refused while the
    # first is still in the queue — the code is spent for good once approved.
    res = submit(review_client, token, bz.id, "INV-TWO", payload=b"i" * 40, code=code)
    assert res.status_code == 409
    assert res.json()["code"] == "invoice_code_used"


# --- 8. the Tier-1 fallback redeems immediately --------------------------------


def test_tier1_fallback_redeems_the_code_on_submission(client, db):
    """With ``REQUIRE_RECEIPT_REVIEW=False`` nothing is queued, so the code is
    spent the moment it is accepted."""
    bz = make_business(db, codes_required=True)
    headers = admin_headers(client)
    code = generate(client, headers, bz.id, count=1)["items"][0]["code"]
    make_user(db, email="fallback-codes@example.com", password="pass12345", must_change_password=False)
    token = login(client, "fallback-codes@example.com", "pass12345")

    res = client.post(
        "/api/v1/transactions",
        headers=auth_headers(token),
        json={"business_id": bz.id, "invoice_number": "INV-FALLBACK", "code": code},
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "approved"
    assert code_status(db, code) == "redeemed"
