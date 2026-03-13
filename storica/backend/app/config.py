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

    # Stage-based model routing
    # Use gemini-2.0-flash everywhere with iteration for quality
    model_essence: str = "gemini-2.0-flash"       # Philosophical foundation
    model_architecture: str = "gemini-2.0-flash"  # Narrative structure
    model_blueprint: str = "gemini-2.0-flash"     # Chapter outlines
    model_chapter: str = "gemini-2.0-flash"       # Prose draft generation
    model_story_bible: str = "gemini-2.0-flash"   # Continuity tracking
    model_prevalidation: str = "gemini-2.0-flash" # Blueprint validation
    model_critique: str = "gemini-2.0-flash"      # Self-review of draft
    model_polish: str = "gemini-2.0-flash"        # Revision based on critique

    # Context window settings
    context_previous_chapters: int = 5            # Number of previous chapters to include
    context_characters_limit: int = 15            # Max characters to show in prompts
    context_previous_ending_chars: int = 1500     # Chars from previous chapter ending

    # The Houses (author profiles directory)
    authors_dir: Path = Path(__file__).parent.parent.parent.parent / "authors"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
