"""Layout guard — measure, don't eyeball.

The editorial design centres every page with equal left/right gutters through
the shared `.container-page` wrapper. A regression (a stray `100vw`, a negative
margin, an over-wide table) shows up as
`document.documentElement.scrollWidth > window.innerWidth`. This test *measures*
that on every page touched by the Tier 2 work, in the real browser.

Run from the repo root:
    cd e2e && ../.venv/bin/python -m pytest test_layout.py -v
"""
from __future__ import annotations

import time

from playwright.sync_api import Page


def _measure(page: Page, path: str) -> None:
    scroll_width, inner_width = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )
    assert scroll_width <= inner_width, (
        f"{path} overflows horizontally: scrollWidth={scroll_width} innerWidth={inner_width}"
    )


def _open(page: Page, app_url: str, path: str) -> None:
    page.goto(f"{app_url}{path}")
    page.wait_for_load_state("load")
    # Let fonts/layout settle. `networkidle` is never reached on pages holding
    # an SSE connection (the admin feed), so a short explicit wait is used.
    page.wait_for_timeout(400)


def _create_volunteer(context, app_url: str) -> tuple[str, str]:
    """Create a dedicated volunteer so this module never depends on another
    test having (or not having) activated the seeded demo account."""
    stamp = int(time.time() * 1000)
    email = f"layout-{stamp}@example.com"
    password = "layout-pass-123"

    login = context.request.post(
        f"{app_url}/api/v1/auth/admin/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert login.ok, login.text()
    token = login.json()["access_token"]

    created = context.request.post(
        f"{app_url}/api/v1/admin/users",
        data={
            "cpr": f"L{stamp % 10**11:011d}",
            "email": email,
            "name": "Layout Tester",
            "password": password,
            "expiry_date": "2099-01-01T00:00:00Z",
            "reward_points": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.ok, created.text()
    return email, password


def _login_volunteer(page: Page, app_url: str, email: str, password: str) -> None:
    _open(page, app_url, "/login")
    page.fill("#identifier", email)
    page.fill("#password", password)
    page.click("button:has-text('Sign in')")

    # New accounts force the first-login activation modal.
    modal = page.locator("div").filter(has_text="Set up your profile").last
    try:
        modal.wait_for(state="visible", timeout=10000)
    except TimeoutError:
        page.wait_for_url("**/profile", timeout=10000)
        return
    modal.locator("input").nth(0).fill("Layout Tester")
    modal.locator("input").nth(1).fill(f"layout-{int(time.time() * 1000)}@example.com")
    modal.locator("input").nth(2).fill("layout-pass-123")
    modal.locator("button:has-text('Save & continue')").click()
    page.wait_for_url("**/profile", timeout=10000)


def test_public_pages_have_balanced_gutters(browser, app_url: str) -> None:
    context = browser.new_context()
    page = context.new_page()
    for path in ("/", "/directory", "/businesses/1"):
        _open(page, app_url, path)
        _measure(page, path)
    context.close()


def test_volunteer_and_admin_pages_have_balanced_gutters(browser, app_url: str) -> None:
    context = browser.new_context()
    page = context.new_page()

    email, password = _create_volunteer(context, app_url)
    _login_volunteer(page, app_url, email, password)
    _measure(page, "/profile")

    admin = context.new_page()
    _open(admin, app_url, "/admin/login")
    admin.fill("#admin-username", "admin")
    admin.fill("#admin-password", "admin123")
    admin.click("button:has-text('Sign in to dashboard')")
    admin.wait_for_url("**/admin", timeout=10000)

    for path in ("/admin", "/admin/reviews"):
        _open(admin, app_url, path)
        _measure(admin, path)
    context.close()