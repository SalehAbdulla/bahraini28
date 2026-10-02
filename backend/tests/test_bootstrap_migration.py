"""Schema reconciliation tests (Tier 1 migration).

`Base.metadata.create_all` never alters an existing table, so a database created
before the anti-fraud work must be migrated by ``reconcile_schema`` on startup.
This test builds the *old* schema by hand (as it exists in production today) and
asserts the migration:

* adds ``businesses.invoice_pattern``;
* tightens invoice uniqueness to ``(business_id, invoice_number)``;
* is idempotent (safe to run on every boot).

Kept as a real test rather than a scratch script so the guarantee survives.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db.bootstrap import reconcile_schema

OLD_SCHEMA = [
    """
    CREATE TABLE businesses (
        id INTEGER PRIMARY KEY,
        name VARCHAR(160),
        commercial_registration VARCHAR(60),
        logo_path VARCHAR(255),
        discount_percentage INTEGER,
        description TEXT,
        is_active BOOLEAN,
        expiry_date DATETIME,
        category_id INTEGER,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        business_id INTEGER,
        invoice_number VARCHAR(64),
        reward_increment INTEGER,
        created_at DATETIME,
        CONSTRAINT uq_user_business_invoice
            UNIQUE (user_id, business_id, invoice_number)
    )
    """,
]


@pytest.fixture()
def legacy_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        for ddl in OLD_SCHEMA:
            conn.execute(text(ddl))
    yield engine
    engine.dispose()
    os.unlink(path)


def _names(engine, table: str) -> set[str]:
    inspector = inspect(engine)
    names = {c["name"] for c in inspector.get_unique_constraints(table)}
    names |= {i["name"] for i in inspector.get_indexes(table)}
    return names


def test_reconcile_adds_invoice_pattern_column(legacy_engine):
    assert "invoice_pattern" not in {
        c["name"] for c in inspect(legacy_engine).get_columns("businesses")
    }

    reconcile_schema(legacy_engine)

    columns = {c["name"] for c in inspect(legacy_engine).get_columns("businesses")}
    assert "invoice_pattern" in columns


def test_reconcile_widens_invoice_uniqueness(legacy_engine):
    assert "uq_business_invoice" not in _names(legacy_engine, "transactions")

    reconcile_schema(legacy_engine)

    # SQLite cannot drop the original table constraint, so the widened rule is
    # enforced with a unique index; Postgres would report a unique constraint.
    assert "uq_business_invoice" in _names(legacy_engine, "transactions")


def test_reconcile_makes_invoice_unique_across_users(legacy_engine):
    reconcile_schema(legacy_engine)

    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO transactions "
                "(user_id, business_id, invoice_number, reward_increment) "
                "VALUES (1, 10, 'X', 1)"
            )
        )

    # A *different* user submitting the same invoice at the same partner must
    # now be rejected — this was the receipt-sharing hole.
    with pytest.raises(Exception):
        with legacy_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO transactions "
                    "(user_id, business_id, invoice_number, reward_increment) "
                    "VALUES (2, 10, 'X', 1)"
                )
            )


def test_reconcile_is_idempotent(legacy_engine):
    reconcile_schema(legacy_engine)
    reconcile_schema(legacy_engine)  # must not raise

    assert "uq_business_invoice" in _names(legacy_engine, "transactions")