"""Schema reconciliation tests (Tier 1 + Tier 2 + Tier 3 migrations).

`Base.metadata.create_all` never alters an existing table, so a database created
before the anti-fraud work must be migrated by ``reconcile_schema`` on startup.
This test builds the *old* schema by hand (as it exists in production) and
asserts the migration:

* adds ``businesses.invoice_pattern``;
* tightens invoice uniqueness to ``(business_id, invoice_number)``;
* adds the Tier 2 review columns and backfills existing rows to ``approved`` so
  no historical reward is lost;
* adds the Tier 3 ``businesses.codes_required`` / ``transactions.code_id`` columns;
* adds ``businesses.discount_label`` (the headline for a non-percentage benefit);
* is idempotent (safe to run on every boot).

The legacy schema is emitted in the dialect of the engine under test, and that
engine follows ``TEST_DATABASE_URL`` (see ``tests/conftest.py``). The same tests
therefore run on SQLite locally *and* on PostgreSQL in CI — which matters,
because the two backends take different branches of every ``if dialect`` in
``app/db/bootstrap.py`` (``DROP CONSTRAINT`` vs ``DROP INDEX``, ``TIMESTAMPTZ``
vs ``DATETIME``, ``BOOLEAN NOT NULL DEFAULT false`` vs ``… DEFAULT 0``), and
PostgreSQL is what production actually runs.

Kept as a real test rather than a scratch script so the guarantee survives.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import Boolean, create_engine, inspect, text

from app.db.base import Base
from app.db.bootstrap import reconcile_schema
from app.models import Admin, InvoiceCode, User


def _legacy_ddl(dialect: str) -> list[str]:
    """The pre-anti-fraud ``businesses`` + ``transactions`` tables.

    Types are dialect-correct. PostgreSQL needs ``SERIAL`` (the tests insert
    rows without an explicit id) and ``TIMESTAMPTZ``: the real legacy database
    was built by ``create_all`` with ``TZDateTime``, so its timestamps are
    timezone-aware — and the Tier 2 backfill copies ``created_at`` straight into
    the new ``reviewed_at`` column, which only compares equal if both sides
    carry the timezone.
    """
    if dialect == "postgresql":
        pk, ts = "SERIAL PRIMARY KEY", "TIMESTAMPTZ"
    else:
        pk, ts = "INTEGER PRIMARY KEY", "DATETIME"

    return [
        f"""
        CREATE TABLE businesses (
            id {pk},
            name VARCHAR(160),
            commercial_registration VARCHAR(60),
            logo_path VARCHAR(255),
            discount_percentage INTEGER,
            description TEXT,
            is_active BOOLEAN,
            expiry_date {ts},
            category_id INTEGER,
            created_at {ts},
            updated_at {ts}
        )
        """,
        f"""
        CREATE TABLE transactions (
            id {pk},
            user_id INTEGER,
            business_id INTEGER,
            invoice_number VARCHAR(64),
            reward_increment INTEGER,
            created_at {ts},
            CONSTRAINT uq_user_business_invoice
                UNIQUE (user_id, business_id, invoice_number)
        )
        """,
    ]


@pytest.fixture()
def legacy_engine():
    """An engine holding only the pre-migration schema.

    Uses ``TEST_DATABASE_URL`` when the suite is pointed at PostgreSQL (as CI's
    postgres job does), otherwise a throwaway SQLite file, so the default local
    run is unchanged.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    path: str | None = None
    if url:
        engine = create_engine(url)
    else:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")

    with engine.begin() as conn:
        for ddl in _legacy_ddl(engine.dialect.name):
            conn.execute(text(ddl))

    try:
        yield engine
    finally:
        # Leave the (possibly shared) database exactly as it was found: the rest
        # of the suite creates these same table names with ``create_all``.
        Base.metadata.drop_all(bind=engine)
        cascade = " CASCADE" if engine.dialect.name == "postgresql" else ""
        with engine.begin() as conn:
            for table in ("transactions", "businesses", "invoice_codes"):
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}"{cascade}'))
        engine.dispose()
        if path is not None:
            os.unlink(path)


@pytest.fixture()
def legacy_engine_with_related(legacy_engine):
    """The legacy tables *plus* ``admins`` / ``users`` / ``invoice_codes``.

    Present so the migration's conditional foreign-key branches run: the
    ``reviewed_by`` → ``admins`` and ``code_id`` → ``invoice_codes`` constraints
    are only attached when the target table already exists.
    """
    Base.metadata.create_all(
        bind=legacy_engine,
        tables=[Admin.__table__, User.__table__, InvoiceCode.__table__],
    )
    yield legacy_engine


def _require_postgres(engine) -> None:
    """Skip unless the suite is pointed at PostgreSQL."""
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-only branch — run with TEST_DATABASE_URL set")


def _names(engine, table: str) -> set[str]:
    inspector = inspect(engine)
    names = {c["name"] for c in inspector.get_unique_constraints(table)}
    names |= {i["name"] for i in inspector.get_indexes(table)}
    return names


def _foreign_keys(engine, table: str) -> dict[tuple[str, ...], dict]:
    return {
        tuple(fk["constrained_columns"]): fk
        for fk in inspect(engine).get_foreign_keys(table)
    }



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

    # Both backends end up enforcing the widened rule; they just report it
    # differently — a unique *constraint* on PostgreSQL, a unique *index* on
    # SQLite (which cannot alter an existing table constraint).
    assert "uq_business_invoice" in _names(legacy_engine, "transactions")
    constraints = {
        c["name"] for c in inspect(legacy_engine).get_unique_constraints("transactions")
    }
    if legacy_engine.dialect.name == "postgresql":
        assert "uq_business_invoice" in constraints
        # The old (stricter, per-user) rule is really gone, not merely shadowed.
        assert "uq_user_business_invoice" not in constraints
    else:
        assert "uq_business_invoice" not in constraints


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


# --- Tier 2: receipt review lifecycle ------------------------------------------

REVIEW_COLUMNS = {
    "status",
    "receipt_path",
    "receipt_sha256",
    "reviewed_by",
    "reviewed_at",
    "rejection_reason",
}


def test_reconcile_adds_review_columns_and_backfills_legacy_rows(legacy_engine):
    """Pre-Tier-2 rows were credited instantly — they must stay ``approved``."""
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO transactions "
                "(user_id, business_id, invoice_number, reward_increment, created_at) "
                "VALUES (1, 10, 'OLD-1', 1, '2024-01-02 03:04:05')"
            )
        )

    before = {c["name"] for c in inspect(legacy_engine).get_columns("transactions")}
    assert REVIEW_COLUMNS.isdisjoint(before)

    reconcile_schema(legacy_engine)

    columns = {c["name"] for c in inspect(legacy_engine).get_columns("transactions")}
    assert REVIEW_COLUMNS <= columns

    with legacy_engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT status, reviewed_at, created_at FROM transactions "
                "WHERE invoice_number = 'OLD-1'"
            )
        ).one()
    assert row[0] == "approved"
    # reviewed_at is stamped from created_at so the ledger order is preserved.
    assert row[1] == row[2]


def test_reconcile_review_columns_is_idempotent(legacy_engine):
    reconcile_schema(legacy_engine)
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO transactions "
                "(user_id, business_id, invoice_number, reward_increment) "
                "VALUES (2, 11, 'NEW-1', 1)"
            )
        )

    reconcile_schema(legacy_engine)  # second boot must not raise

    columns = {c["name"] for c in inspect(legacy_engine).get_columns("transactions")}
    assert REVIEW_COLUMNS <= columns
    # The explicit status set by the application is never overwritten by a
    # later boot (the backfill only runs on the boot that adds the column).
    with legacy_engine.begin() as conn:
        conn.execute(
            text("UPDATE transactions SET status = 'rejected' WHERE invoice_number = 'NEW-1'")
        )
    reconcile_schema(legacy_engine)
    with legacy_engine.begin() as conn:
        status = conn.execute(
            text("SELECT status FROM transactions WHERE invoice_number = 'NEW-1'")
        ).scalar()
    assert status == "rejected"


# --- Tier 3: single-use receipt codes ------------------------------------------


def test_reconcile_adds_code_columns(legacy_engine):
    assert "codes_required" not in {
        c["name"] for c in inspect(legacy_engine).get_columns("businesses")
    }
    assert "code_id" not in {
        c["name"] for c in inspect(legacy_engine).get_columns("transactions")
    }

    reconcile_schema(legacy_engine)

    assert "codes_required" in {
        c["name"] for c in inspect(legacy_engine).get_columns("businesses")
    }
    assert "code_id" in {
        c["name"] for c in inspect(legacy_engine).get_columns("transactions")
    }


def test_reconcile_code_flag_defaults_to_off_for_legacy_rows(legacy_engine):
    """Existing partners must keep the free-typed invoice flow (Tier 1/2)."""
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO businesses (id, name, discount_percentage) "
                "VALUES (1, 'Legacy Partner', 10)"
            )
        )

    reconcile_schema(legacy_engine)

    with legacy_engine.begin() as conn:
        flag = conn.execute(
            text("SELECT codes_required FROM businesses WHERE id = 1")
        ).scalar()
    assert flag in (0, False)


def test_reconcile_code_columns_is_idempotent(legacy_engine):
    reconcile_schema(legacy_engine)
    reconcile_schema(legacy_engine)  # second boot must not raise

    assert "codes_required" in {
        c["name"] for c in inspect(legacy_engine).get_columns("businesses")
    }
    assert "code_id" in {
        c["name"] for c in inspect(legacy_engine).get_columns("transactions")
    }


def test_reconcile_adds_the_discount_label_column(legacy_engine):
    """A partner whose benefit is not a percentage is described by a label.

    Nullable on purpose: every pre-existing partner keeps "no label" and simply
    goes on showing its percentage.
    """
    reconcile_schema(legacy_engine)
    reconcile_schema(legacy_engine)  # second boot must not raise

    columns = {c["name"]: c for c in inspect(legacy_engine).get_columns("businesses")}
    assert columns["discount_label"]["nullable"] is True


# --- PostgreSQL-specific branches ----------------------------------------------
# Production runs PostgreSQL, so these are the branches that actually execute on
# a real deploy; SQLite takes the other side of every ``if dialect == ...`` in
# ``app/db/bootstrap.py``. Each skips (with a reason) on a SQLite run.


def test_postgres_drops_the_old_constraint(legacy_engine):
    _require_postgres(legacy_engine)

    reconcile_schema(legacy_engine)

    constraints = {
        c["name"] for c in inspect(legacy_engine).get_unique_constraints("transactions")
    }
    assert "uq_user_business_invoice" not in constraints
    assert "uq_business_invoice" in constraints


def test_postgres_code_flag_is_a_not_null_boolean(legacy_engine):
    _require_postgres(legacy_engine)

    reconcile_schema(legacy_engine)

    column = {
        c["name"]: c for c in inspect(legacy_engine).get_columns("businesses")
    }["codes_required"]
    assert isinstance(column["type"], Boolean)
    assert column["nullable"] is False
    # Rendered as ``DEFAULT false``, so every existing partner stays opted out.
    assert column["default"] is not None


def test_postgres_reviewed_at_is_timezone_aware(legacy_engine):
    """``TIMESTAMPTZ`` (not a bare ``DATETIME``) is what the model expects."""
    _require_postgres(legacy_engine)

    reconcile_schema(legacy_engine)

    column = {
        c["name"]: c for c in inspect(legacy_engine).get_columns("transactions")
    }["reviewed_at"]
    assert getattr(column["type"], "timezone", False) is True


def test_postgres_attaches_the_reviewed_by_foreign_key(legacy_engine_with_related):
    _require_postgres(legacy_engine_with_related)

    reconcile_schema(legacy_engine_with_related)

    fks = _foreign_keys(legacy_engine_with_related, "transactions")
    assert ("reviewed_by",) in fks
    assert fks[("reviewed_by",)]["referred_table"] == "admins"
    assert fks[("reviewed_by",)]["options"].get("ondelete") == "SET NULL"


def test_postgres_attaches_the_code_id_foreign_key(legacy_engine_with_related):
    _require_postgres(legacy_engine_with_related)

    reconcile_schema(legacy_engine_with_related)

    fks = _foreign_keys(legacy_engine_with_related, "transactions")
    assert ("code_id",) in fks
    assert fks[("code_id",)]["referred_table"] == "invoice_codes"
    assert fks[("code_id",)]["options"].get("ondelete") == "SET NULL"


def test_migration_runs_with_related_tables_on_every_dialect(legacy_engine_with_related):
    """The ``REFERENCES … ON DELETE SET NULL`` DDL must be valid on both backends.

    This is the branch that only fires when ``admins`` / ``invoice_codes``
    already exist — i.e. exactly the state of a real pre-Tier-3 database.
    """
    reconcile_schema(legacy_engine_with_related)

    columns = {
        c["name"]
        for c in inspect(legacy_engine_with_related).get_columns("transactions")
    }
    assert {"reviewed_by", "reviewed_at", "code_id"} <= columns