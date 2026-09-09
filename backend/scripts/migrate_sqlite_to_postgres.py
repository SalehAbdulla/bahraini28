"""Copy existing SQLite data into the configured PostgreSQL database.

Use to migrate any local SQLite database produced by the dev setup once the
production PostgreSQL instance exists:

    cd backend
    SQLITE_SOURCE=/path/to/bahraini28.db \\
    DATABASE_URL=postgresql+psycopg://bahraini28:<pw>@postgres:5432/bahraini28 \\
    PYTHONPATH=. python scripts/migrate_sqlite_to_postgres.py

For existing data it truncates the destination tables and re-inserts them in
dependency order, then re-syncs PostgreSQL autoincrement sequences, so it is
safe to re-run. Tables that don't exist yet are created first (idempotent).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.types import BigInteger, Integer

from app.core.config import get_settings
from app.db.base import Base
# Importing the model modules registers their tables on Base.metadata —
# without this, create_all() and the copy loop would run against nothing.
from app.models import (  # noqa: F401
    Admin,
    Area,
    Business,
    BusinessArea,
    Category,
    RewardAdjustment,
    Transaction,
    User,
)


def main() -> None:
    settings = get_settings()
    dest_url = settings.DATABASE_URL
    if not dest_url.startswith("postgresql"):
        sys.exit("This script migrates SQLite -> PostgreSQL only (set DATABASE_URL).")

    source = os.environ.get("SQLITE_SOURCE", "bahraini28.db")
    if not Path(source).exists():
        print(f"No SQLite file at {source!r} — nothing to migrate.")
        return

    src_engine = create_engine(f"sqlite:///{source}")
    dest_engine = create_engine(dest_url, pool_pre_ping=True)

    # Ensure the destination schema exists (no-op for existing tables).
    Base.metadata.create_all(bind=dest_engine)

    with src_engine.connect() as src_conn, dest_engine.begin() as dest_conn:
        # Cleanup pass (children before parents): clears previous runs without
        # tripping foreign-key constraints.
        for table in reversed(list(Base.metadata.sorted_tables)):
            dest_conn.execute(table.delete())

        # Copy pass (parents before children): FK-safe insertion order.
        for table in Base.metadata.sorted_tables:
            rows = [dict(row) for row in src_conn.execute(table.select()).mappings()]
            if not rows:
                print(f"  {table.name}: 0 rows (skip)")
                continue

            dest_conn.execute(table.insert(), rows)

            # Re-sync autoincrement sequences for tables with a single integer PK.
            pk_cols = list(table.primary_key.columns)
            if len(pk_cols) == 1 and isinstance(pk_cols[0].type, (Integer, BigInteger)):
                pk_name = pk_cols[0].name
                seq = dest_conn.execute(
                    text(f"SELECT pg_get_serial_sequence('{table.name}', '{pk_name}')")
                ).scalar()
                if seq:
                    max_id = dest_conn.execute(
                        text(f'SELECT COALESCE(MAX("{pk_name}"), 0) FROM "{table.name}"')
                    ).scalar() or 0
                    dest_conn.execute(text(f"SELECT setval('{seq}', {max_id})"))

            print(f"  {table.name}: {len(rows)} rows copied")

    print(f"Migration complete: {source} -> {dest_url.split('//')[1].split('@')[-1]}")


if __name__ == "__main__":
    main()
