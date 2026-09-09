"""Admin business management tests: register / list / update partnerships."""
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


def _payload(category_id: int, *, cr="CR-NEW-001", name="New Partner", **overrides) -> dict:
    payload = {
        "name": name,
        "commercial_registration": cr,
        "category_id": category_id,
        "discount_percentage": 15,
        "description": "A brand-new partner.",
        "expiry_date": "2099-01-01T00:00:00Z",
        "is_active": True,
        "branches": [],
    }
    payload.update(overrides)
    return payload


def test_admin_can_register_business_with_branches(client, db):
    category_id = make_business(db, cr="CR-EXISTING").category_id
    area = make_area(db, "Riffa")
    res = client.post(
        "/api/v1/admin/businesses",
        headers=_auth(client),
        json=_payload(
            category_id,
            branches=[
                {
                    "area_id": area.id,
                    "branch_name": "Riffa Mall",
                    "address": "Avenue 1",
                    "phone": "+973 123",
                }
            ],
        ),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "New Partner"
    assert body["commercial_registration"] == "CR-NEW-001"
    assert body["discount_percentage"] == 15
    assert body["is_active"] is True
    assert len(body["branches"]) == 1
    assert body["branches"][0]["area_name"] == "Riffa"
    assert body["branches"][0]["branch_name"] == "Riffa Mall"


def test_admin_register_duplicate_commercial_registration_conflict(client, db):
    category_id = make_business(db, cr="CR-DUP").category_id
    res = client.post(
        "/api/v1/admin/businesses", headers=_auth(client), json=_payload(category_id, cr="CR-DUP")
    )
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_business"


def test_admin_register_unknown_category_not_found(client, db):
    res = client.post(
        "/api/v1/admin/businesses", headers=_auth(client), json=_payload(category_id=99999)
    )
    assert res.status_code == 404
    assert res.json()["code"] == "category_not_found"


def test_admin_register_unknown_area_not_found(client, db):
    category_id = make_business(db, cr="CR-AREA").category_id
    res = client.post(
        "/api/v1/admin/businesses",
        headers=_auth(client),
        json=_payload(category_id, branches=[{"area_id": 99999}]),
    )
    assert res.status_code == 404
    assert res.json()["code"] == "area_not_found"


def test_admin_list_businesses_includes_inactive_and_filters(client, db):
    make_business(db, name="Active Co", cr="CR-L1", is_active=True)
    make_business(db, name="Retired Co", cr="CR-L2", is_active=False)

    all_items = client.get("/api/v1/admin/businesses", headers=_auth(client)).json()
    names = {i["name"] for i in all_items["items"]}
    assert {"Active Co", "Retired Co"} <= names

    inactive = client.get(
        "/api/v1/admin/businesses?status=inactive", headers=_auth(client)
    ).json()
    assert all(i["name"] == "Retired Co" for i in inactive["items"])

    search = client.get(
        "/api/v1/admin/businesses?search=Retired", headers=_auth(client)
    ).json()
    assert search["total"] == 1


def test_admin_can_update_business_and_replace_branches(client, db):
    bz = make_business(db, name="Edit Me", cr="CR-UPD", discount=10)
    area = make_area(db, "Manama")
    headers = _auth(client)

    res = client.put(
        f"/api/v1/admin/businesses/{bz.id}",
        headers=headers,
        json={
            "name": "Edited Name",
            "discount_percentage": 22,
            "is_active": False,
            "branches": [{"area_id": area.id, "branch_name": "Downtown"}],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Edited Name"
    assert body["discount_percentage"] == 22
    assert body["is_active"] is False
    assert [x["branch_name"] for x in body["branches"]] == ["Downtown"]

    # Replacing with an empty list clears all branches.
    res2 = client.put(
        f"/api/v1/admin/businesses/{bz.id}", headers=headers, json={"branches": []}
    )
    assert res2.status_code == 200
    assert res2.json()["branches"] == []


def test_admin_update_duplicate_cr_conflict(client, db):
    a = make_business(db, name="A", cr="CR-X1")
    make_business(db, name="B", cr="CR-X2")
    res = client.put(
        f"/api/v1/admin/businesses/{a.id}",
        headers=_auth(client),
        json={"commercial_registration": "CR-X2"},
    )
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_business"


def test_user_token_cannot_manage_businesses(client, db):
    make_user(db, email="regular@example.com", password="pass12345", must_change_password=False)
    user_token = login(client, "regular@example.com", "pass12345")
    headers = auth_headers(user_token)
    assert client.post("/api/v1/admin/businesses", headers=headers, json=_payload(1)).status_code in (401, 403)
    assert client.get("/api/v1/admin/businesses", headers=headers).status_code in (401, 403)


def test_admin_upload_business_logo(client, db):
    bz = make_business(db, name="Logo Co", cr="CR-LOGO1")
    res = client.post(
        f"/api/v1/admin/businesses/{bz.id}/logo",
        headers=_auth(client),
        files={"file": ("logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")},
    )
    assert res.status_code == 200, res.text
    assert res.json()["logo_url"].startswith("/uploads/")

    # Uploading again replaces the file (still a single logo_url, no error).
    res2 = client.post(
        f"/api/v1/admin/businesses/{bz.id}/logo",
        headers=_auth(client),
        files={"file": ("new.png", b"\x89PNG\r\n\x1a\n" + b"\x01" * 64, "image/png")},
    )
    assert res2.status_code == 200
    assert res2.json()["logo_url"].startswith("/uploads/")
    assert res2.json()["logo_url"] != res.json()["logo_url"]


def test_admin_upload_logo_rejects_unsupported_type(client, db):
    bz = make_business(db, cr="CR-LOGO2")
    res = client.post(
        f"/api/v1/admin/businesses/{bz.id}/logo",
        headers=_auth(client),
        files={"file": ("note.txt", b"plain text, not an image", "text/plain")},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "unsupported_file_type"


def test_admin_upload_logo_rejects_oversized_file(client, db):
    bz = make_business(db, cr="CR-LOGO3")
    res = client.post(
        f"/api/v1/admin/businesses/{bz.id}/logo",
        headers=_auth(client),
        files={"file": ("big.png", b"\xff" * (3 * 1024 * 1024), "image/png")},
    )
    assert res.status_code == 413
    assert res.json()["code"] == "file_too_large"


def test_user_token_cannot_upload_logo(client, db):
    bz = make_business(db, cr="CR-LOGO4")
    make_user(db, email="uploader@example.com", password="pass12345", must_change_password=False)
    user_token = login(client, "uploader@example.com", "pass12345")
    res = client.post(
        f"/api/v1/admin/businesses/{bz.id}/logo",
        headers=auth_headers(user_token),
        files={"file": ("logo.png", b"png", "image/png")},
    )
    assert res.status_code in (401, 403)
