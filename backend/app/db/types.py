"""Custom SQLAlchemy types.

``TZDateTime`` stores datetimes as UTC and *always* returns timezone-aware
(datetime.UTC) values back to the application:

- SQLite has no native timezone support, so values are stored as naive UTC and
  re-attached on read.
- PostgreSQL (via the ``timestamptz`` backing) stores them correctly.

This avoids the classic "can't compare offset-naive and offset-aware" error
when SQLite is used locally while keeping full awareness on Postgres.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class TZDateTime(TypeDecorator):
    """DateTime that round-trips as aware UTC regardless of the dialect."""

    # timezone=True renders TIMESTAMPTZ on PostgreSQL; SQLite ignores the flag
    # and stores the naive UTC produced in ``process_bind_param``.
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            if dialect.name == "sqlite":
                # SQLite cannot store tz offsets; persist naive UTC instead.
                value = value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value