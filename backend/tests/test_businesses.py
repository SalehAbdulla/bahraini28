"""Public business directory tests: listing with filters and detail view."""
from __future__ import annotations

from tests.conftest import make_area, make_business


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
    assert body["discount_percentage"] == 10
    assert body["areas"][0]["area_name"] == "Manama"


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