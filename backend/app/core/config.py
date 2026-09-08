"""Application settings loaded from environment variables / .env file.

Uses pydantic-settings (the standard settings layer for FastAPI projects).
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    APP_NAME: str = "Beyond Education"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # --- Security ----------------------------------------------------------
    SECRET_KEY: str = "dev-only-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BCRYPT_ROUNDS: int = 12

    # --- Database ----------------------------------------------------------
    # Defaults to a local SQLite file; set DATABASE_URL to a PostgreSQL
    # DSN (e.g. postgresql+psycopg://user:pass@host/db) for production.
    DATABASE_URL: str = "sqlite:///./bahraini28.db"
    DB_ECHO: bool = False

    # --- Business rules ----------------------------------------------------
    # Timezone used to compute the start of the "current calendar day" for
    # the per-business daily usage limit.
    DEFAULT_TIMEZONE: str = "Asia/Bahrain"
    # Maximum number of successful uses per business per calendar day.
    DAILY_LIMIT_PER_BUSINESS: int = 3

    # --- Assets -------------------------------------------------------------
    # Directors for uploaded business logos (served at /uploads).
    UPLOAD_DIR: str = "backend/uploads"
    MAX_UPLOAD_SIZE_MB: int = 2

    # --- CORS --------------------------------------------------------------
    # Frontend origins allowed to call this API. The Vite dev server runs on
    # port 5173 by default; in production add the deployed frontend origin.
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
        ]
    )

    # --- Bootstrap ---------------------------------------------------------
    # When True, an initial admin account is created on startup if none exist.
    SEED_DEFAULT_ADMIN: bool = True
    ADMIN_INITIAL_USERNAME: str = "admin"
    ADMIN_INITIAL_PASSWORD: str = "admin123"
    ADMIN_INITIAL_NAME: str = "System Administrator"


@lru_cache
def get_settings() -> Settings:
    return Settings()
