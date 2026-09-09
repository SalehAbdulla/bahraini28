"""E2E fixtures: boot the real stack (FastAPI on :8000 + Vite dev server on
:5173) against a throwaway seeded SQLite database, and drive it with
Playwright Chromium.

Run from the repo root:
    cd e2e && ../.venv/bin/python -m pytest -v

Overrides: E2E_BACKEND_PORT / E2E_FRONTEND_PORT / E2E_BASE_URL.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Generator

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

BACKEND_PORT = int(os.environ.get("E2E_BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("E2E_FRONTEND_PORT", "5173"))
# Explicit IPv4: Playwright/Chromium may resolve "localhost" to ::1, which the
# vite dev server (IPv4-only by default) refuses.
BASE_URL = os.environ.get("E2E_BASE_URL") or f"http://127.0.0.1:{FRONTEND_PORT}"


def wait_http(url: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.5)
    raise TimeoutError(f"timed out waiting for {url}: {last_err}")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Allow binding while a previous run's socket is still in TIME_WAIT.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


@pytest.fixture(scope="session")
def e2e_tmp_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("e2e")


@pytest.fixture(scope="session")
def backend_process(e2e_tmp_dir: Path) -> Generator[int, None, None]:
    if not port_free(BACKEND_PORT):
        pytest.skip(f"port {BACKEND_PORT} busy — set E2E_BACKEND_PORT")

    db_path = e2e_tmp_dir / "e2e.db"
    uploads = e2e_tmp_dir / "uploads"
    uploads.mkdir(exist_ok=True)

    env = dict(os.environ)
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "SEED_DEFAULT_ADMIN": "true",
            "ADMIN_INITIAL_USERNAME": "admin",
            "ADMIN_INITIAL_PASSWORD": "admin123",
            "UPLOAD_DIR": str(uploads),
            "PYTHONPATH": str(BACKEND),
        }
    )

    # Seed demo businesses + volunteer (volunteer@example.com / volunteer123).
    seed = subprocess.run(
        [sys.executable, "scripts/seed.py"],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if seed.returncode != 0:
        raise RuntimeError(f"seed.py failed:\n{seed.stdout}\n{seed.stderr}")

    log = open(e2e_tmp_dir / "backend.log", "w")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_http(f"http://127.0.0.1:{BACKEND_PORT}/health")
        yield BACKEND_PORT
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


@pytest.fixture(scope="session")
def frontend_process(backend_process: int, e2e_tmp_dir: Path) -> Generator[int, None, None]:
    if not port_free(FRONTEND_PORT):
        pytest.skip(f"port {FRONTEND_PORT} busy — set E2E_FRONTEND_PORT")

    log = open(e2e_tmp_dir / "vite.log", "w")
    proc = subprocess.Popen(
        [
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(FRONTEND_PORT),
            "--strictPort",
        ],
        cwd=str(FRONTEND),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_http(f"http://127.0.0.1:{FRONTEND_PORT}/")
        yield FRONTEND_PORT
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


@pytest.fixture(scope="session")
def browser(frontend_process: int) -> Generator[Any, None, None]:
    """Chromium driving the real stack — depends on the server fixtures (which
    in turn boot the seeded backend on :8000 and vite on :5173)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture()
def app_url() -> str:
    return BASE_URL
