"""Storage Port - interface for persistence operations."""

from abc import ABC, abstractmethod
from typing import Optional, List
from ..domain import (
    Project,
    PipelineRun,
    PhaseResult,
    StoryBible,
    Chapter,
)


class StoragePort(ABC):
    """Abstract interface for storage operations."""

    # Project operations
    @abstractmethod
    async def get_project(self, project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        pass

    @abstractmethod
    async def save_project(self, project: Project) -> Project:
        """Save/update a project."""
        pass

    @abstractmethod
    async def list_projects(self, user_id: int) -> List[Project]:
        """List all projects for a user."""
        pass

    # Pipeline run operations
    @abstractmethod
    async def get_pipeline_run(self, project_id: int) -> Optional[PipelineRun]:
        """Get the current pipeline run for a project."""
        pass

    @abstractmethod
    async def save_pipeline_run(self, run: PipelineRun) -> PipelineRun:
        """Save/update a pipeline run."""
        pass

    @abstractmethod
    async def save_phase_result(
        self,
        project_id: int,
        result: PhaseResult
    ) -> PhaseResult:
        """Save a phase result."""
        pass

    # Chapter operations
    @abstractmethod
    async def get_chapter(
        self,
        project_id: int,
        chapter_number: int
    ) -> Optional[Chapter]:
        """Get a specific chapter."""
        pass

    @abstractmethod
    async def save_chapter(
        self,
        project_id: int,
        chapter: Chapter
    ) -> Chapter:
        """Save/update a chapter."""
        pass

    @abstractmethod
    async def list_chapters(self, project_id: int) -> List[Chapter]:
        """List all chapters for a project."""
        pass

    # Story Bible operations
    @abstractmethod
    async def get_story_bible(self, project_id: int) -> Optional[StoryBible]:
        """Get the story bible for a project."""
        pass

    @abstractmethod
    async def save_story_bible(self, bible: StoryBible) -> StoryBible:
        """Save/update the story bible."""
        pass
