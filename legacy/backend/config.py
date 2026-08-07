"""Application configuration."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "sqlite:///./storica.db"

    # Redis/Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # JWT Auth
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Anthropic API
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL_DEFAULT: str = "claude-sonnet-4-20250514"
    CLAUDE_MODEL_PROSE: str = "claude-opus-4-20250514"

    # Pipeline settings
    PIPELINE_MAX_ITERATIONS: int = 3
    PIPELINE_PASSING_THRESHOLD: float = 7.0
    PIPELINE_APPROVAL_TIMEOUT_SECONDS: int = 3600  # 1 hour

    # Cost limits
    MAX_COST_PER_PROJECT: float = 50.0  # USD
    WARN_COST_THRESHOLD: float = 25.0  # USD

    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
