"""
Dependency Injection Container.

This is where all dependencies are wired together.
"""

from functools import lru_cache
from pathlib import Path

from .config import settings
from .core.usecases import GenerateStoryUseCase, ApprovePhaseUseCase
from .adapters import (
    AnthropicLLMAdapter,
    SQLAlchemyStorageAdapter,
    WebSocketEventAdapter,
    YAMLAuthorAdapter,
)
from .prompts import PromptEngine

# Import agents package to trigger registration
import app.agents  # noqa: F401


class Container:
    """
    Dependency injection container.

    Provides factory methods for creating use cases with all dependencies.
    """

    def __init__(self):
        """Initialize container with adapters."""
        self._llm = AnthropicLLMAdapter(
            api_key=settings.ANTHROPIC_API_KEY,
            default_model="sonnet",
        )

        authors_dir = Path(__file__).parent / "authors" / "profiles"
        self._authors = YAMLAuthorAdapter(str(authors_dir))

        templates_dir = Path(__file__).parent / "prompts" / "templates"
        self._prompt_engine = PromptEngine(str(templates_dir))

        # Connection manager (set by app startup)
        self._connection_manager = None

    def set_connection_manager(self, manager) -> None:
        """Set WebSocket connection manager."""
        self._connection_manager = manager

    def get_generate_story_usecase(self, session) -> GenerateStoryUseCase:
        """
        Get GenerateStoryUseCase with all dependencies.

        Args:
            session: Database session

        Returns:
            Configured use case
        """
        storage = SQLAlchemyStorageAdapter(session)
        events = WebSocketEventAdapter(self._connection_manager)

        return GenerateStoryUseCase(
            llm=self._llm,
            storage=storage,
            events=events,
            authors=self._authors,
            prompt_engine=self._prompt_engine,
        )

    def get_approve_phase_usecase(self, session) -> ApprovePhaseUseCase:
        """
        Get ApprovePhaseUseCase with all dependencies.

        Args:
            session: Database session

        Returns:
            Configured use case
        """
        storage = SQLAlchemyStorageAdapter(session)
        events = WebSocketEventAdapter(self._connection_manager)

        return ApprovePhaseUseCase(
            storage=storage,
            events=events,
        )

    @property
    def llm(self) -> AnthropicLLMAdapter:
        return self._llm

    @property
    def authors(self) -> YAMLAuthorAdapter:
        return self._authors

    @property
    def prompt_engine(self) -> PromptEngine:
        return self._prompt_engine


@lru_cache()
def get_container() -> Container:
    """Get the global container instance."""
    return Container()
