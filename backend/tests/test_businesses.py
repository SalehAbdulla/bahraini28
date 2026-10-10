"""Public business directory tests: listing with filters and detail view.

The directory itself is public, but the exact member benefit (the discount) is
a **member-only reveal** — these tests pin both halves: anonymous callers get
``None``, a valid logged-in member gets the real figure.
"""
from __future__ import annotations

from tests.conftest import PAST, auth_headers, login, make_area, make_business, make_user


def member_headers(client, db, email="member@example.com") -> dict:
    """Log in a valid volunteer and return the bearer headers."""
    make_user(db, email=email, password="pass12345", must_change_password=False)
    return auth_headers(login(client, email, "pass12345"))


def seed_directory(db):
    manama = make_area(db, "Manama")
    riffa = make_area(db, "Riffa")
    b1 = make_business(db, name="Alpha", cr="CR-ALPHA", discount=10, area=manama)
    b2 = make_business(db, name="Beta", cr="CR-BETA", discount=25)
    # inactive businesses are hidden from the public list
    make_business(db, name="Hidden", cr="CR-HIDE", is_active=False)
    return manama, riffa, b1, b2


def test_list_businesses_public(client, db):
    seed_directory(db)
    res = client.get("/api/v1/businesses")
    assert res.status_code == 200
    body = res.json()
    # only the two active ones, alphabetical
    assert body["total"] == 2
    assert [b["name"] for b in body["items"]] == ["Alpha", "Beta"]


def test_filter_businesses_by_category(client, db):
    seed_directory(db)
    res = client.get("/api/v1/businesses?category=test-cat")
    assert res.status_code == 200
    assert res.json()["total"] == 2


def test_filter_businesses_by_area(client, db):
    manama, _riffa, _b1, _b2 = seed_directory(db)
    # Note: only Alpha is linked to Manama.
    res = client.get(f"/api/v1/businesses?area_id={manama.id}")
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_search_businesses(client, db):
    seed_directory(db)
    res = client.get("/api/v1/businesses?q=beta")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["name"] == "Beta"


def test_business_detail(client, db):
    manama, _riffa, b1, _b2 = seed_directory(db)
    res = client.get(f"/api/v1/businesses/{b1.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Alpha"
    assert body["areas"][0]["area_name"] == "Manama"
    # Anonymous: the exact member benefit is not disclosed.
    assert body["discount_percentage"] is None


def test_business_detail_reveals_the_discount_to_a_member(client, db):
    _manama, _riffa, b1, _b2 = seed_directory(db)
    res = client.get(f"/api/v1/businesses/{b1.id}", headers=member_headers(client, db))
    assert res.status_code == 200
    assert res.json()["discount_percentage"] == 10


def test_anonymous_detail_hides_the_offer_wording(client, db):
    """For the pilot partners the offer text lives in ``description``
    (``seed_partners`` sets ``description=offer``), so it is part of the
    member-only reveal — otherwise it leaks the very discount we hide."""
    bz = make_business(db, name="Watches", cr="CR-DESC", discount=25)
    bz.description = "خصم 25%"
    db.add(bz)
    db.commit()

    anon = client.get(f"/api/v1/businesses/{bz.id}").json()
    assert anon["description"] is None
    assert anon["discount_percentage"] is None

    member = client.get(
        f"/api/v1/businesses/{bz.id}", headers=member_headers(client, db)
    ).json()
    assert member["description"] == "خصم 25%"
    assert member["discount_percentage"] == 25


def test_anonymous_listing_hides_the_benefit(client, db):
    """The directory is public, but the discount figures are not."""
    seed_directory(db)
    items = client.get("/api/v1/businesses").json()["items"]
    assert items
    assert all(b["discount_percentage"] is None for b in items)
    assert all(b["discount_label"] is None for b in items)


def test_member_listing_reveals_the_benefit(client, db):
    seed_directory(db)
    items = client.get("/api/v1/businesses", headers=member_headers(client, db)).json()["items"]
    by_name = {b["name"]: b for b in items}
    assert by_name["Alpha"]["discount_percentage"] == 10
    assert by_name["Beta"]["discount_percentage"] == 25


def test_invalid_token_is_treated_as_anonymous(client, db):
    """A stale/garbage token must not 401 a public page — it degrades to the
    redacted anonymous view instead."""
    seed_directory(db)
    res = client.get(
        "/api/v1/businesses", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert res.status_code == 200
    assert res.json()["items"][0]["discount_percentage"] is None


def test_expired_member_sees_the_redacted_view(client, db):
    """Expiry is enforced for the reveal exactly as it is for login."""
    seed_directory(db)
    user = make_user(
        db, email="expired@example.com", password="pass12345", must_change_password=False
    )
    headers = auth_headers(login(client, "expired@example.com", "pass12345"))
    # Expire the membership *after* login (login itself blocks expired accounts).
    db.refresh(user)
    user.expiry_date = PAST
    db.add(user)
    db.commit()

    res = client.get("/api/v1/businesses", headers=headers)
    assert res.status_code == 200
    assert res.json()["items"][0]["discount_percentage"] is None


def test_public_payloads_carry_the_benefit_label(client, db):
    """A partner whose benefit is not a percentage carries it as a label, so the
    directory can print that instead of a nonsensical "-0%"."""
    bz = make_business(
        db, name="Hospital", cr="CR-LABEL", discount=0, discount_label="خدمات مختارة"
    )
    headers = member_headers(client, db)

    summary = client.get("/api/v1/businesses", headers=headers).json()["items"][0]
    assert summary["discount_percentage"] == 0
    assert summary["discount_label"] == "خدمات مختارة"

    detail = client.get(f"/api/v1/businesses/{bz.id}", headers=headers).json()
    assert detail["discount_label"] == "خدمات مختارة"


def test_percentage_only_partner_has_no_label(client, db):
    bz = make_business(db, name="Cafe", cr="CR-PLAIN", discount=20)
    headers = member_headers(client, db)

    assert (
        client.get("/api/v1/businesses", headers=headers).json()["items"][0]["discount_label"]
        is None
    )
    assert (
        client.get(f"/api/v1/businesses/{bz.id}", headers=headers).json()["discount_label"]
        is None
    )


def test_business_detail_not_found(client, db):
    res = client.get("/api/v1/businesses/999999")
    assert res.status_code == 404


def test_business_categories_and_areas(client, db):
    seed_directory(db)
    res = client.get("/api/v1/businesses/categories")
    assert res.status_code == 200
    assert any(c["slug"] == "test-cat" for c in res.json())

    res = client.get("/api/v1/businesses/areas")
    assert res.status_code == 200
    assert {"Manama", "Riffa"}.issubset({a["name"] for a in res.json()})