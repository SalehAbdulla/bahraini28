"""Idempotent post-``create_all`` schema reconciliation.

``Base.metadata.create_all`` creates *missing tables* but never alters an
existing one, and this project ships no migration tool. This module applies the
small, additive changes introduced by the Tier 1 anti-fraud work to databases
that already exist, so a deploy needs no manual SQL:

* ``businesses.invoice_pattern`` column (per-partner invoice regex).
* ``transactions`` unique constraint widened from
  ``(user_id, business_id, invoice_number)`` to ``(business_id, invoice_number)``
  so an invoice can only ever be credited once per business, by anyone.

Both steps are guarded by an inspector so they run at most once and are no-ops
on a fresh database. Failures are swallowed and logged: a reconciliation
problem must never stop the app from booting.
"""
from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)

_INVOICE_COLUMN = "invoice_pattern"
_OLD_CONSTRAINT = "uq_user_business_invoice"
_NEW_CONSTRAINT = "uq_business_invoice"


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


def reconcile_schema(engine: Engine) -> None:
    """Apply additive Tier 1 schema changes to an existing database."""
    for step in (_ensure_invoice_pattern_column, _widen_invoice_uniqueness):
        try:
            step(engine)
        except Exception:  # noqa: BLE001 - never block startup on reconciliation
            logger.exception("bootstrap: %s failed", step.__name__)