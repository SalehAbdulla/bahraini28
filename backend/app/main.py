"""FastAPI application entrypoint.

Factory pattern: ``create_app()`` builds a fresh app (used by uvicorn and by
the test suite, which swaps in an in-memory database engine).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, businesses, notifications, transactions, users
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.base import Base
from app.db.session import create_session_factory, get_db


def _exception_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "code": "validation_error", "errors": exc.errors()},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    ``settings`` is injectable so tests can point at an in-memory DB and a
    known timezone / daily limit without touching environment variables.
    """
    settings = settings or get_settings()

    engine, SessionLocal = create_session_factory(settings)

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.SessionLocal = SessionLocal

    # --- database session dependency (overridable in tests) ----------------
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db

    # --- CORS ----------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- routes ----------------------------------------------------------------
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    app.include_router(auth.router, prefix=settings.API_PREFIX)
    app.include_router(users.router, prefix=settings.API_PREFIX)
    app.include_router(businesses.router, prefix=settings.API_PREFIX)
    app.include_router(transactions.router, prefix=settings.API_PREFIX)
    app.include_router(notifications.router, prefix=settings.API_PREFIX)
    app.include_router(admin.router, prefix=settings.API_PREFIX)

    # --- health check ----------------------------------------------------------
    @app.get("/health", tags=["System"], include_in_schema=False)
    def health():
        return {"status": "ok", "service": settings.APP_NAME}

    # --- exception handlers -----------------------------------------------------
    app.add_exception_handler(AppError, _exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)

    # --- startup: create tables + bootstrap admin -------------------------------
    @app.on_event("startup")
    def on_startup() -> None:
        Base.metadata.create_all(bind=engine)
        if settings.SEED_DEFAULT_ADMIN:
            from app.core.security import hash_password
            from app.models import Admin
            from sqlalchemy import select

            with SessionLocal() as db:
                if db.scalar(select(Admin).where(Admin.username == settings.ADMIN_INITIAL_USERNAME)):
                    return
                db.add(
                    Admin(
                        username=settings.ADMIN_INITIAL_USERNAME,
                        name=settings.ADMIN_INITIAL_NAME,
                        password_hash=hash_password(settings.ADMIN_INITIAL_PASSWORD),
                        is_superuser=True,
                    )
                )
                db.commit()

    return app


app = create_app()