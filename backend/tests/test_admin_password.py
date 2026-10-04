"""Admin credential tests: self-service rotation + the ops recovery script.

The deployment runbook tells operators to *"change the admin password"* before
setting ``SEED_DEFAULT_ADMIN=false`` — but ``POST /auth/change-password`` is a
volunteer route (an admin token is rejected) and the admin API only resets a
**volunteer's** password. These tests cover the two paths that make the
instruction achievable:

1. an admin rotating their own password from the dashboard (current one required);
2. ``scripts/set_admin_password.py`` — the first rotation and lost-password
   recovery, plus the CLI's password resolution (flag → env → hidden prompt).
"""
from __future__ import annotations

import argparse
import getpass
import sys
import types

import pytest

from app.core.errors import AdminNotFoundError
from app.core.security import verify_password
from app.services import admin as admin_service
from scripts.set_admin_password import _resolve_password
from tests.conftest import admin_login, auth_headers, login, make_user

NEW_PASSWORD = "rotated-pass-123"
BOOTSTRAP_PASSWORD = "admin123"


def _admin_headers(client) -> dict:
    return auth_headers(admin_login(client))


def _change(client, headers, current: str, new: str):
    return client.post(
        "/api/v1/admin/me/password",
        headers=headers,
        json={"current_password": current, "new_password": new},
    )


def _admin_login_status(client, password: str) -> int:
    return client.post(
        "/api/v1/auth/admin/login", json={"username": "admin", "password": password}
    ).status_code


# --- 1. self-service rotation --------------------------------------------------


def test_admin_can_change_their_own_password(client):
    res = _change(client, _admin_headers(client), BOOTSTRAP_PASSWORD, NEW_PASSWORD)
    assert res.status_code == 204, res.text

    # The old password is dead; the new one works.
    assert _admin_login_status(client, BOOTSTRAP_PASSWORD) == 401
    assert _admin_login_status(client, NEW_PASSWORD) == 200


def test_wrong_current_password_is_rejected(client):
    res = _change(client, _admin_headers(client), "not-my-password", NEW_PASSWORD)
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_current_password"
    # ... and nothing changed.
    assert _admin_login_status(client, BOOTSTRAP_PASSWORD) == 200


def test_a_too_short_new_password_is_rejected(client):
    res = _change(client, _admin_headers(client), BOOTSTRAP_PASSWORD, "short")
    assert res.status_code == 422


def test_a_volunteer_token_cannot_rotate_an_admin_password(client, db):
    make_user(db, email="nosy@example.com", password="pass12345", must_change_password=False)
    user_token = login(client, "nosy@example.com", "pass12345")

    res = _change(client, auth_headers(user_token), BOOTSTRAP_PASSWORD, NEW_PASSWORD)
    assert res.status_code == 401
    assert _admin_login_status(client, BOOTSTRAP_PASSWORD) == 200


# --- 2. the recovery / provisioning path ---------------------------------------


def test_set_admin_password_replaces_the_hash(client, db):
    admin = admin_service.set_admin_password(
        db, username="admin", new_password=NEW_PASSWORD
    )
    assert verify_password(NEW_PASSWORD, admin.password_hash)
    assert not verify_password(BOOTSTRAP_PASSWORD, admin.password_hash)


def test_set_admin_password_for_an_unknown_username_raises(client, db):
    with pytest.raises(AdminNotFoundError):
        admin_service.set_admin_password(db, username="nobody", new_password=NEW_PASSWORD)


# --- 3. the CLI's password resolution (no database touched) --------------------


def _args(password: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(username="admin", password=password)


def test_cli_prefers_the_explicit_flag(monkeypatch):
    monkeypatch.setenv("ADMIN_NEW_PASSWORD", "from-env-123")
    assert _resolve_password(_args(password="from-flag-123")) == "from-flag-123"


def test_cli_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("ADMIN_NEW_PASSWORD", "from-env-123")
    assert _resolve_password(_args()) == "from-env-123"


def test_cli_refuses_when_it_cannot_prompt(monkeypatch):
    monkeypatch.delenv("ADMIN_NEW_PASSWORD", raising=False)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: False))
    with pytest.raises(SystemExit):
        _resolve_password(_args())


def test_cli_prompts_twice_and_requires_a_match(monkeypatch):
    monkeypatch.delenv("ADMIN_NEW_PASSWORD", raising=False)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "prompted-123")
    assert _resolve_password(_args()) == "prompted-123"

    replies = iter(["prompted-123", "different-456"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(replies))
    with pytest.raises(SystemExit):
        _resolve_password(_args())
