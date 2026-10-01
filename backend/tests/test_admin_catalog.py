"""Admin catalog management tests: areas & categories CRUD + guards."""
from __future__ import annotations

from tests.conftest import (
    admin_login,
    auth_headers,
    login,
    make_area,
    make_business,
    make_user,
)


def _auth(client) -> dict:
    return auth_headers(admin_login(client))


# --- Areas --------------------------------------------------------------------


def test_admin_can_create_and_list_area(client, db):
    res = client.post("/api/v1/admin/areas", headers=_auth(client), json={"name": "Hamala"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Hamala"
    assert body["is_active"] is True

    listing = client.get("/api/v1/admin/areas", headers=_auth(client))
    assert listing.status_code == 200
    assert any(a["name"] == "Hamala" for a in listing.json())


def test_created_area_is_visible_in_public_directory(client, db):
    client.post("/api/v1/admin/areas", headers=_auth(client), json={"name": "Zallaq"})
    public = client.get("/api/v1/businesses/areas")
    assert public.status_code == 200
    assert any(a["name"] == "Zallaq" for a in public.json())


def test_duplicate_area_name_conflicts(client, db):
    headers = _auth(client)
    client.post("/api/v1/admin/areas", headers=headers, json={"name": "Budaiya"})
    res = client.post("/api/v1/admin/areas", headers=headers, json={"name": "budaiya"})
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_area"


def test_admin_can_rename_and_deactivate_area(client, db):
    headers = _auth(client)
    area_id = client.post(
        "/api/v1/admin/areas", headers=headers, json={"name": "Old Name"}
    ).json()["id"]

    res = client.put(
        f"/api/v1/admin/areas/{area_id}",
        headers=headers,
        json={"name": "New Name", "is_active": False},
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "New Name"
    assert res.json()["is_active"] is False

    # A deactivated area is hidden from the public filter list.
    public = client.get("/api/v1/businesses/areas").json()
    assert all(a["name"] != "New Name" for a in public)


def test_deleting_area_in_use_is_blocked(client, db):
    headers = _auth(client)
    area = make_area(db, "Seef")
    make_business(db, cr="CR-AREA-1", area=area)

    res = client.delete(f"/api/v1/admin/areas/{area.id}", headers=headers)
    assert res.status_code == 409
    assert res.json()["code"] == "area_in_use"


def test_admin_can_delete_unused_area(client, db):
    headers = _auth(client)
    area = make_area(db, "Unused Area")
    res = client.delete(f"/api/v1/admin/areas/{area.id}", headers=headers)
    assert res.status_code == 204

    listing = client.get("/api/v1/admin/areas", headers=headers).json()
    assert all(a["id"] != area.id for a in listing)


# --- Categories ---------------------------------------------------------------


def test_admin_can_create_category_with_generated_slug(client, db):
    res = client.post(
        "/api/v1/admin/categories",
        headers=_auth(client),
        json={"name": "Electronics", "description": "Devices & gadgets"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Electronics"
    assert body["slug"] == "electronics"
    assert body["description"] == "Devices & gadgets"


def test_duplicate_category_name_conflicts(client, db):
    headers = _auth(client)
    client.post("/api/v1/admin/categories", headers=headers, json={"name": "Toys"})
    res = client.post("/api/v1/admin/categories", headers=headers, json={"name": "toys"})
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_category"


def test_admin_can_update_category(client, db):
    headers = _auth(client)
    category_id = client.post(
        "/api/v1/admin/categories", headers=headers, json={"name": "Pets"}
    ).json()["id"]

    res = client.put(
        f"/api/v1/admin/categories/{category_id}",
        headers=headers,
        json={"name": "Pet Care", "slug": "pet-care"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Pet Care"
    assert res.json()["slug"] == "pet-care"


def test_deleting_category_in_use_is_blocked(client, db):
    headers = _auth(client)
    business = make_business(db, cr="CR-CAT-1")

    res = client.delete(
        f"/api/v1/admin/categories/{business.category_id}", headers=headers
    )
    assert res.status_code == 409
    assert res.json()["code"] == "category_in_use"


def test_admin_can_delete_unused_category(client, db):
    headers = _auth(client)
    category_id = client.post(
        "/api/v1/admin/categories", headers=headers, json={"name": "Temporary"}
    ).json()["id"]

    res = client.delete(f"/api/v1/admin/categories/{category_id}", headers=headers)
    assert res.status_code == 204


def test_unknown_area_and_category_return_404(client, db):
    headers = _auth(client)
    assert client.delete("/api/v1/admin/areas/9999", headers=headers).status_code == 404
    assert (
        client.put(
            "/api/v1/admin/categories/9999", headers=headers, json={"name": "Nope"}
        ).status_code
        == 404
    )


def test_user_token_cannot_manage_catalog(client, db):
    make_user(db, email="member@example.com", password="member123", must_change_password=False)
    token = login(client, "member@example.com", "member123")

    res = client.post(
        "/api/v1/admin/areas",
        headers=auth_headers(token),
        json={"name": "Forbidden"},
    )
    assert res.status_code == 401
