"""Cross-test isolation on a persistent ``TEST_DATABASE_URL``.

The default in-memory SQLite engine is rebuilt for every test, so committed
state cannot leak between tests. A persistent database (a file locally, and
PostgreSQL in CI's ``backend-postgres`` job) is shared by the whole session
instead — and that is where this bit us: ``test_admin_password.py`` rotates the
bootstrap admin's password, which then broke the *later* tests in that module
(they log in with the pristine ``admin123``).

These two tests are deliberately order-dependent: the first mutates the shared
database, the second proves the ``app`` fixture handed it a clean slate. That
ordering is the property under test — see ``reset_schema`` in ``conftest.py``.
"""
from __future__ import annotations

from tests.conftest import admin_login, auth_headers

ROTATED_PASSWORD = "isolation-rotated-123"


def test_first_rotates_the_bootstrap_admin(client):
    """Mutate the one row the whole session shares on a persistent database."""
    token = admin_login(client)
    res = client.post(
        "/api/v1/admin/me/password",
        headers=auth_headers(token),
        json={"current_password": "admin123", "new_password": ROTATED_PASSWORD},
    )
    assert res.status_code == 204, res.text
    # The bootstrap password is now dead in *this* test's database...
    assert client.post(
        "/api/v1/auth/admin/login", json={"username": "admin", "password": "admin123"}
    ).status_code == 401


def test_second_gets_a_pristine_bootstrap_admin(client):
    """...and must be back for the next test's fresh ``app`` fixture.

    ``admin_login`` asserts a 200, so this fails if the rotation leaked — i.e.
    it fails on a persistent database unless ``reset_schema`` runs between tests.
    """
    assert admin_login(client)
