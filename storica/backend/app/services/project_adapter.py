"""Database project adapter - replaces file-based storage with DB operations."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ContentType, ProjectStage
from app.services.project import ProjectService


class DatabaseProjectAdapter:
    """Adapter that provides project state management via database.

    This replaces the file-based Project class from the CLI version,
    providing the same interface but storing data in PostgreSQL.
    """

    def __init__(self, db: AsyncSession, project_id: int):
        self.db = db
        self.project_id = project_id
        self._service = ProjectService(db)

    # Essence
    async def get_essence(self) -> Optional[str]:
        """Get the project's essence document."""
        content = await self._service.get_content(
            self.project_id, ContentType.ESSENCE
        )
        return content.content if content else None

    async def save_essence(self, content: str) -> None:
        """Save essence content."""
        await self._service.save_content(
            self.project_id, ContentType.ESSENCE, content
        )

    # Architecture
    async def get_architecture(self) -> Optional[str]:
        """Get the project's architecture document."""
        content = await self._service.get_content(
            self.project_id, ContentType.ARCHITECTURE
        )
        return content.content if content else None

    async def save_architecture(self, content: str) -> None:
        """Save architecture content."""
        await self._service.save_content(
            self.project_id, ContentType.ARCHITECTURE, content
        )

    # Story Bible
    async def get_story_bible(self) -> Optional[str]:
        """Get the project's story bible."""
        content = await self._service.get_content(
            self.project_id, ContentType.STORY_BIBLE
        )
        return content.content if content else None

    async def save_story_bible(self, content: str) -> None:
        """Save story bible content."""
        await self._service.save_content(
            self.project_id, ContentType.STORY_BIBLE, content
        )

    # Blueprints
    async def get_blueprint(self, chapter_num: int) -> Optional[str]:
        """Get a chapter blueprint."""
        blueprint = await self._service.get_blueprint(self.project_id, chapter_num)
        return blueprint.content if blueprint else None

    async def save_blueprint(self, chapter_num: int, content: str) -> None:
        """Save a chapter blueprint."""
        await self._service.save_blueprint(self.project_id, chapter_num, content)

    async def get_all_blueprints(self) -> dict[int, str]:
        """Get all blueprints as a dict of chapter_num -> content."""
        blueprints = await self._service.get_all_blueprints(self.project_id)
        return {bp.chapter_num: bp.content for bp in blueprints}

    # Chapters
    async def get_chapter(self, chapter_num: int) -> Optional[str]:
        """Get a chapter's content."""
        chapter = await self._service.get_chapter(self.project_id, chapter_num)
        return chapter.content if chapter else None

    async def save_chapter(self, chapter_num: int, content: str) -> None:
        """Save a chapter."""
        word_count = len(content.split())
        await self._service.save_chapter(
            self.project_id, chapter_num, content, word_count
        )

    async def get_all_chapters(self) -> dict[int, str]:
        """Get all chapters as a dict of chapter_num -> content."""
        chapters = await self._service.get_all_chapters(self.project_id)
        return {ch.chapter_num: ch.content for ch in chapters}

    async def get_previous_chapters(
        self, current_chapter: int, limit: int = 2
    ) -> list[str]:
        """Get previous chapters for context."""
        chapters = await self._service.get_all_chapters(self.project_id)
        relevant = [
            ch.content
            for ch in chapters
            if ch.chapter_num < current_chapter
        ]
        return relevant[-limit:] if limit else relevant

    # Stage management
    async def update_stage(
        self,
        stage: ProjectStage,
        current_chapter: Optional[int] = None,
        total_chapters: Optional[int] = None,
    ) -> None:
        """Update the project's current stage."""
        await self._service.update_stage(
            self.project_id,
            stage,
            current_chapter,
            total_chapters,
        )

    # Statistics
    async def get_total_word_count(self) -> int:
        """Get total word count across all chapters."""
        chapters = await self._service.get_all_chapters(self.project_id)
        return sum(ch.word_count for ch in chapters)

    async def compile_novel(self) -> str:
        """Compile all chapters into a single document."""
        chapters = await self._service.get_all_chapters(self.project_id)
        parts = []
        for chapter in sorted(chapters, key=lambda c: c.chapter_num):
            parts.append(f"# Chapter {chapter.chapter_num}\n\n{chapter.content}")
        return "\n\n---\n\n".join(parts)
