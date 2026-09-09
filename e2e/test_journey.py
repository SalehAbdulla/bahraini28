"""End-to-end browser tests.

Covers the volunteer journey (login -> first-login activation modal ->
directory -> invoice submit -> profile reward) and the admin dashboard SSE
feed (a purchase made while the dashboard is open is broadcast live).

Requires the fixtures in conftest.py, which boot the real backend + frontend.
Run from the repo root:
    cd e2e && ../.venv/bin/python -m pytest -v
"""
from __future__ import annotations

import time

from playwright.sync_api import Page, expect

VOLUNTEER_EMAIL = "volunteer@example.com"
VOLUNTEER_PASSWORD = "volunteer123"


def _login_as_volunteer(page: Page, app_url: str) -> None:
    page.goto(f"{app_url}/login")
    page.fill("#identifier", VOLUNTEER_EMAIL)
    page.fill("#password", VOLUNTEER_PASSWORD)
    page.click("button:has-text('Sign in')")


def _activate_if_needed(page: Page) -> None:
    """First-login modal: required on accounts with must_change_password=True.

    Waits for the login outcome so we never race the async login request —
    either the modal appears, or the login lands on /profile directly.
    """
    modal = page.locator("div").filter(has_text="Set up your profile").last
    try:
        modal.wait_for(state="visible", timeout=10000)
    except TimeoutError:
        page.wait_for_url("**/profile", timeout=10000)
        return

    modal.locator("input").nth(0).fill("E2E Tester")
    modal.locator("input").nth(1).fill(f"e2e-{int(time.time() * 1000)}@example.com")
    modal.locator("input").nth(2).fill("e2e-pass-123")
    modal.locator("button:has-text('Save & continue')").click()
    page.wait_for_url("**/profile", timeout=10000)


def _submit_invoice(page: Page, prefix: str) -> str:
    invoice = f"{prefix}-{int(time.time() * 1000)}"
    page.fill("input[placeholder='Invoice number']", invoice)
    page.click("button:has-text('Submit invoice')")
    expect(page.get_by_text("Invoice verified! +1 reward")).to_be_visible(timeout=10000)
    return invoice


def test_volunteer_journey(browser, app_url: str) -> None:
    context = browser.new_context()
    page = context.new_page()

    # --- login triggers the compulsory first-login activation modal ---------
    _login_as_volunteer(page, app_url)
    expect(page.get_by_text("Set up your profile")).to_be_visible(timeout=10000)
    _activate_if_needed(page)
    expect(page.get_by_role("heading", name="E2E Tester")).to_be_visible(timeout=10000)

    # --- directory -> business detail ----------------------------------------
    page.goto(f"{app_url}/directory")
    expect(page.get_by_role("heading", name="Partner Directory")).to_be_visible()
    first_card = page.locator("a[href^='/businesses/']").first
    business_name = first_card.locator("h3").inner_text()
    first_card.click()
    expect(page.get_by_role("heading", name=business_name)).to_be_visible(timeout=10000)

    # --- invoice submission ----------------------------------------------------
    invoice = _submit_invoice(page, "E2E")

    # --- profile reflects the +1 reward and the history row --------------------
    page.goto(f"{app_url}/profile")
    reward_card = page.locator("div").filter(has_text="Reward points").last
    expect(reward_card).to_contain_text("1")
    expect(page.get_by_text(invoice)).to_be_visible()
    context.close()


def test_admin_registers_business(browser, app_url: str) -> None:
    context = browser.new_context()
    page = context.new_page()

    # --- admin login via UI ------------------------------------------------
    page.goto(f"{app_url}/admin/login")
    page.fill("#admin-username", "admin")
    page.fill("#admin-password", "admin123")
    page.click("button:has-text('Sign in to dashboard')")
    expect(page.get_by_text("Admin Dashboard")).to_be_visible(timeout=10000)

    # --- open business management -------------------------------------------
    page.click("a:has-text('Businesses')")
    expect(page.get_by_role("heading", name="Business Management")).to_be_visible(timeout=10000)

    # --- register a new partnership ------------------------------------------
    page.click("button:has-text('Register business')")
    stamp = int(time.time() * 1000)
    page.get_by_label("Business name").fill(f"E2E Store {stamp}")
    page.get_by_label("Commercial registration").fill(f"CR-E2E-{stamp}")
    page.get_by_label("Category").select_option(index=1)
    page.get_by_label("Discount %").fill("12")
    page.locator("button:has-text('Save business')").click()

    # --- the new partnership appears in the management table -----------------
    expect(page.get_by_text(f"E2E Store {stamp}")).to_be_visible(timeout=10000)
    expect(page.get_by_text(f"CR-E2E-{stamp}")).to_be_visible()
    context.close()


def test_admin_dashboard_sse_feed(browser, app_url: str) -> None:
    context = browser.new_context()

    # --- admin login + dashboard opens the live SSE feed ----------------------
    admin_page = context.new_page()
    admin_page.goto(f"{app_url}/admin/login")
    admin_page.fill("#admin-username", "admin")
    admin_page.fill("#admin-password", "admin123")
    admin_page.click("button:has-text('Sign in to dashboard')")
    expect(admin_page.get_by_text("Admin Dashboard")).to_be_visible(timeout=10000)
    # EventSource connects (admin JWT passed via ?_token=).
    expect(admin_page.get_by_text("Live", exact=False)).to_be_visible(timeout=15000)

    # --- create a dedicated volunteer via the admin API (hermetic test) --------
    stamp = int(time.time() * 1000)
    admin_login = context.request.post(
        f"{app_url}/api/v1/auth/admin/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert admin_login.ok, admin_login.text()
    admin_token = admin_login.json()["access_token"]

    create = context.request.post(
        f"{app_url}/api/v1/admin/users",
        data={
            "cpr": f"E2E{stamp % 10_000_000}",
            "email": f"sse-{stamp}@example.com",
            "name": "SSE Volunteer",
            "password": "sse-pass-123",
            "expiry_date": "2099-01-01T00:00:00Z",
            "reward_points": 0,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create.ok, create.text()

    # --- volunteer makes a purchase while the dashboard is open ----------------
    user_page = context.new_page()
    user_page.goto(f"{app_url}/login")
    user_page.fill("#identifier", f"sse-{stamp}@example.com")
    user_page.fill("#password", "sse-pass-123")
    user_page.click("button:has-text('Sign in')")
    _activate_if_needed(user_page)
    user_page.goto(f"{app_url}/businesses/1")
    invoice = _submit_invoice(user_page, "SSE")

    # --- the alert broadcasts to the dashboard in real time --------------------
    expect(admin_page.get_by_text(invoice)).to_be_visible(timeout=15000)
    context.close()
