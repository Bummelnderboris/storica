"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Storica"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database (The Archives)
    database_url: str = "postgresql+asyncpg://storica:storica@localhost:5432/storica"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT
    jwt_secret_key: str = "jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM
    gemini_api_key: Optional[str] = None
    default_model: str = "gemini-2.0-flash"

    # The Houses (author profiles directory)
    authors_dir: Path = Path(__file__).parent.parent.parent.parent / "authors"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
