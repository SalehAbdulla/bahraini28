"""Idempotent post-``create_all`` schema reconciliation.

``Base.metadata.create_all`` creates *missing tables* but never alters an
existing one, and this project ships no migration tool. This module applies the
small, additive changes introduced by the anti-fraud work to databases that
already exist, so a deploy needs no manual SQL:

Tier 1 (``docs/ANTI_FRAUD_PLAN.md``)
* ``businesses.invoice_pattern`` column (per-partner invoice regex).
* ``transactions`` unique constraint widened from
  ``(user_id, business_id, invoice_number)`` to ``(business_id, invoice_number)``
  so an invoice can only ever be credited once per business, by anyone.

Tier 2 (receipt proof + admin approval)
* ``transactions.status`` / ``receipt_path`` / ``receipt_sha256`` /
  ``reviewed_by`` / ``reviewed_at`` / ``rejection_reason`` columns, plus the
  backfill that marks every pre-existing row ``approved`` (those rewards were
  credited instantly under Tier 1 and must not disappear).

Tier 3 (single-use merchant receipt codes)
* ``businesses.codes_required`` (per-partner opt-in) and ``transactions.code_id``
  (the code a submission spent). The ``invoice_codes`` table itself is *new*, so
  ``create_all`` builds it; only the two columns need reconciling here.

Partner benefits
* ``businesses.discount_label`` — the short headline shown instead of the
  percentage for partners whose benefit is not a flat percentage ("Special
  offer", free weekly ice cream, ...). Their ``discount_percentage`` stays 0.

Every step is guarded by an inspector so it runs at most once and is a no-op on
a fresh database. Failures are swallowed and logged: a reconciliation problem
must never stop the app from booting.
"""
from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)

_INVOICE_COLUMN = "invoice_pattern"
_OLD_CONSTRAINT = "uq_user_business_invoice"
_NEW_CONSTRAINT = "uq_business_invoice"
_DISCOUNT_LABEL_COLUMN = "discount_label"

#: Tier 2 columns added to ``transactions``: ``(name, type)``. ``reviewed_at``
#: is rendered with the dialect's timestamp type and ``reviewed_by`` gains its
#: foreign key only when ``admins`` already exists.
_REVIEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("status", "VARCHAR(16)"),
    ("receipt_path", "VARCHAR(255)"),
    ("receipt_sha256", "VARCHAR(64)"),
    ("reviewed_by", "INTEGER"),
    ("reviewed_at", "DATETIME"),
    ("rejection_reason", "TEXT"),
)


def _quote(identifier: str) -> str:
    """Minimal identifier quoting — names here are internal constants."""
    return '"' + identifier.replace('"', "") + '"'


def _ensure_invoice_pattern_column(engine: Engine) -> None:
    inspector = inspect(engine)
    if "businesses" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("businesses")}
    if _INVOICE_COLUMN in columns:
        return
    with engine.begin() as conn:
        conn.execute(
            text(f"ALTER TABLE businesses ADD COLUMN {_quote(_INVOICE_COLUMN)} VARCHAR(160)")
        )
    logger.info("bootstrap: added businesses.%s", _INVOICE_COLUMN)


def _widen_invoice_uniqueness(engine: Engine) -> None:
    """Swap the per-user unique constraint for a per-business one.

    Uses ``DROP CONSTRAINT IF EXISTS`` where supported and falls back to
    ``DROP INDEX IF EXISTS`` for backends that model the constraint as a unique
    index (namely SQLite).
    """
    inspector = inspect(engine)
    if "transactions" not in inspector.get_table_names():
        return

    names = {c["name"] for c in inspector.get_unique_constraints("transactions")}
    names |= {i["name"] for i in inspector.get_indexes("transactions")}

    old_present = _OLD_CONSTRAINT in names
    new_present = _NEW_CONSTRAINT in names
    if not old_present and new_present:
        return

    dialect = engine.dialect.name
    with engine.begin() as conn:
        if old_present:
            if dialect == "postgresql":
                conn.execute(
                    text(
                        f"ALTER TABLE transactions DROP CONSTRAINT IF EXISTS {_quote(_OLD_CONSTRAINT)}"
                    )
                )
            else:
                # SQLite cannot drop a table constraint; the old (stricter,
                # per-user) rule is left in place — it is a harmless subset of
                # the new rule, which the unique index below enforces.
                conn.execute(text(f"DROP INDEX IF EXISTS {_quote(_OLD_CONSTRAINT)}"))

        if not new_present:
            if dialect == "sqlite":
                # SQLite cannot add a constraint to an existing table; a unique
                # index enforces exactly the same rule.
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        f"{_quote(_NEW_CONSTRAINT)} "
                        "ON transactions (business_id, invoice_number)"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE transactions ADD CONSTRAINT "
                        f"{_quote(_NEW_CONSTRAINT)} "
                        "UNIQUE (business_id, invoice_number)"
                    )
                )
    logger.info("bootstrap: ensured unique(business_id, invoice_number) on transactions")


def _ensure_review_columns(engine: Engine) -> None:
    """Add the Tier 2 review lifecycle columns, then backfill legacy rows.

    Existing rows were credited *instantly* under Tier 1, so they are stamped
    ``approved`` with ``reviewed_at = created_at`` — otherwise every historical
    reward would silently stop counting as spendable.
    """
    inspector = inspect(engine)
    if "transactions" not in inspector.get_table_names():
        return

    present = {c["name"] for c in inspector.get_columns("transactions")}
    tables = set(inspector.get_table_names())
    timestamp_type = "TIMESTAMPTZ" if engine.dialect.name == "postgresql" else "DATETIME"
    added: list[str] = []

    with engine.begin() as conn:
        for name, column_type in _REVIEW_COLUMNS:
            if name in present:
                continue
            if name == "reviewed_at":
                column_type = timestamp_type
            elif name == "reviewed_by" and "admins" in tables:
                # SQLite/Postgres both allow a REFERENCES clause on ADD COLUMN
                # as long as the default is NULL, which is the case here.
                column_type = f"{column_type} REFERENCES admins(id) ON DELETE SET NULL"
            conn.execute(
                text(
                    f"ALTER TABLE transactions ADD COLUMN "
                    f"{_quote(name)} {column_type}"
                )
            )
            added.append(name)

        # Mirror the model's ``index=True`` on status / receipt_sha256; on a
        # fresh database ``create_all`` already created these exact names.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_status "
                "ON transactions (status)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_receipt_sha256 "
                "ON transactions (receipt_sha256)"
            )
        )

        # Backfill once — only meaningful on the boot that adds ``status``.
        if "status" in added:
            conn.execute(
                text("UPDATE transactions SET status = 'approved' WHERE status IS NULL")
            )
            conn.execute(
                text(
                    "UPDATE transactions SET reviewed_at = created_at "
                    "WHERE reviewed_at IS NULL"
                )
            )

    if added:
        logger.info("bootstrap: added transactions columns %s", ", ".join(added))


def _ensure_code_columns(engine: Engine) -> None:
    """Add the Tier 3 columns (per-partner ``codes_required`` + ``code_id``).

    ``invoice_codes`` is a brand-new table, so ``create_all`` has already built
    it; only the two new columns on *existing* tables are reconciled here.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    # Dialect-appropriate literal for the ``NOT NULL DEFAULT`` on the new flag.
    bool_default = "false" if engine.dialect.name == "postgresql" else "0"

    if "businesses" in tables:
        columns = {c["name"] for c in inspector.get_columns("businesses")}
        if "codes_required" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        'ALTER TABLE businesses ADD COLUMN "codes_required" '
                        f"BOOLEAN NOT NULL DEFAULT {bool_default}"
                    )
                )
            logger.info("bootstrap: added businesses.codes_required")

    if "transactions" in tables:
        columns = {c["name"] for c in inspector.get_columns("transactions")}
        if "code_id" not in columns:
            # Attach the FK only when its target table already exists, so the
            # migration also works against a pre-Tier-3 schema in isolation.
            column_type = "INTEGER"
            if "invoice_codes" in tables:
                column_type = "INTEGER REFERENCES invoice_codes(id) ON DELETE SET NULL"
            with engine.begin() as conn:
                conn.execute(
                    text(f'ALTER TABLE transactions ADD COLUMN "code_id" {column_type}')
                )
            logger.info("bootstrap: added transactions.code_id")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_transactions_code_id "
                    "ON transactions (code_id)"
                )
            )


def _ensure_discount_label_column(engine: Engine) -> None:
    """Add ``businesses.discount_label`` (short non-percentage benefit headline)."""
    inspector = inspect(engine)
    if "businesses" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("businesses")}
    if _DISCOUNT_LABEL_COLUMN in columns:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                f"ALTER TABLE businesses ADD COLUMN {_quote(_DISCOUNT_LABEL_COLUMN)} "
                "VARCHAR(40)"
            )
        )
    logger.info("bootstrap: added businesses.%s", _DISCOUNT_LABEL_COLUMN)


def reconcile_schema(engine: Engine) -> None:
    """Apply additive schema changes (Tier 1 + Tier 2) to an existing database."""
    for step in (
        _ensure_invoice_pattern_column,
        _widen_invoice_uniqueness,
        _ensure_review_columns,
        _ensure_code_columns,
        _ensure_discount_label_column,
    ):
        try:
            step(engine)
        except Exception:  # noqa: BLE001 - never block startup on reconciliation
            logger.exception("bootstrap: %s failed", step.__name__)