"""Rotate an administrator's password from the command line.

``POST /api/v1/auth/change-password`` is a *volunteer* route and the admin API
only resets a **volunteer's** password, so this is the escape hatch the
deployment runbook needs:

* replace the bootstrap password ``deploy/.env`` generated, **before** the first
  login — when no admin UI session exists yet;
* recover an admin account whose password has been lost.

Local use (from the backend/ directory):

    cd backend
    PYTHONPATH=. ../.venv/bin/python scripts/set_admin_password.py --username admin

Inside the deployed stack:

    docker compose -f deploy/docker-compose.yml run --rm backend \\
        python scripts/set_admin_password.py --username admin

The new password is prompted for twice (hidden) unless ``--password`` or the
``ADMIN_NEW_PASSWORD`` environment variable is supplied for non-interactive use.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.core.errors import AdminNotFoundError
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.admin import set_admin_password

#: Matches the API schema (``schemas.admin.AdminPasswordChangeRequest``): bcrypt
#: only reads the first 72 bytes, so longer input is refused rather than silently
#: truncated to something the operator did not type.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72


def _resolve_password(args: argparse.Namespace) -> str:
    """Return the new password, prompting (twice, hidden) when not supplied."""
    if args.password:
        return args.password
    from_env = os.environ.get("ADMIN_NEW_PASSWORD")
    if from_env:
        return from_env
    if not sys.stdin.isatty():
        raise SystemExit(
            "No password supplied and stdin is not a terminal "
            "(pass --password or set ADMIN_NEW_PASSWORD)."
        )
    first = getpass.getpass(f"New password for {args.username!r}: ")
    second = getpass.getpass("Repeat the new password: ")
    if first != second:
        raise SystemExit("The two passwords do not match.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set (or reset) an administrator's password."
    )
    parser.add_argument(
        "--username", default="admin", help="the admin username (default: admin)"
    )
    parser.add_argument(
        "--password",
        default=None,
        help="the new password; omit to be prompted (or set ADMIN_NEW_PASSWORD)",
    )
    args = parser.parse_args(argv)

    password = _resolve_password(args)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise SystemExit(
            f"The password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters."
        )

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            admin = set_admin_password(db, username=args.username, new_password=password)
        except AdminNotFoundError as exc:
            print(f"error: {exc.message}", file=sys.stderr)
            return 1
        username, admin_id = admin.username, admin.id

    print(f"Password updated for admin {username!r} (id={admin_id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
