"""Database engine and session management.

The engine is built lazily from the active settings. Tests create their own
app instance with an in-memory engine and override the ``get_db`` dependency,
which is the canonical FastAPI testing pattern.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings


def make_session_factory(database_url: str, echo: bool = False):
    """Build an SQLAlchemy engine + sessionmaker for the given DSN."""
    connect_args = {}
    pool_kwargs: dict = {}
    if database_url.startswith("sqlite"):
        # SQLite does not allow shared connections across threads by default.
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            # A single shared in-memory connection so all sessions see the
            # same database (used by the test suite).
            pool_kwargs["poolclass"] = StaticPool

    engine = create_engine(
        database_url,
        echo=echo,
        connect_args=connect_args,
        pool_pre_ping=True,
        **pool_kwargs,
    )
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_settings = get_settings()
engine, SessionLocal = make_session_factory(_settings.DATABASE_URL, _settings.DB_ECHO)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_session_factory(settings: Settings):
    """Create a fresh engine + sessionmaker for a given settings object."""
    return make_session_factory(settings.DATABASE_URL, settings.DB_ECHO)
