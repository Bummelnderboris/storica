"""Configuration management for LitAI."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel


class Config(BaseModel):
    """Application configuration."""

    projects_dir: Path = Path.home() / ".litai" / "projects"
    authors_dir: Path = Path(__file__).parent.parent.parent.parent / "authors"
    gemini_api_key: Optional[str] = None
    default_model: str = "gemini-2.0-flash"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment."""
        load_dotenv()

        config = cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
        )

        # Override paths if set in environment
        if projects_dir := os.getenv("LITAI_PROJECTS_DIR"):
            config.projects_dir = Path(projects_dir)
        if authors_dir := os.getenv("LITAI_AUTHORS_DIR"):
            config.authors_dir = Path(authors_dir)

        # Ensure directories exist
        config.projects_dir.mkdir(parents=True, exist_ok=True)

        return config
