"""Project service for CRUD operations."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import (
    Blueprint,
    Chapter,
    ContentType,
    Project,
    ProjectContent,
    ProjectStage,
)
from app.schemas.project import (
    ContentSummary,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectUpdate,
)


class ProjectService:
    """Service for project operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_project(self, user_id: int, data: ProjectCreate) -> Project:
        """Create a new project."""
        project = Project(
            user_id=user_id,
            name=data.name,
            author_id=data.author_id,
            target_words=data.target_words,
            seed=data.seed,
            current_stage=ProjectStage.ESSENCE,
        )
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def get_project(self, project_id: int, user_id: int) -> Optional[Project]:
        """Get a project by ID, ensuring user owns it."""
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_project_with_details(
        self, project_id: int, user_id: int
    ) -> Optional[ProjectDetailResponse]:
        """Get a project with content summary."""
        project = await self.get_project(project_id, user_id)
        if not project:
            return None

        # Get content counts
        content_result = await self.db.execute(
            select(ProjectContent.content_type).where(
                ProjectContent.project_id == project_id
            )
        )
        content_types = [r[0] for r in content_result.all()]

        blueprint_count_result = await self.db.execute(
            select(func.count(Blueprint.id)).where(Blueprint.project_id == project_id)
        )
        blueprint_count = blueprint_count_result.scalar() or 0

        chapter_result = await self.db.execute(
            select(func.count(Chapter.id), func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.project_id == project_id
            )
        )
        chapter_row = chapter_result.one()
        chapter_count = chapter_row[0] or 0
        total_word_count = chapter_row[1] or 0

        content_summary = ContentSummary(
            has_essence=ContentType.ESSENCE in content_types,
            has_architecture=ContentType.ARCHITECTURE in content_types,
            has_story_bible=ContentType.STORY_BIBLE in content_types,
            blueprint_count=blueprint_count,
            chapter_count=chapter_count,
            total_word_count=total_word_count,
        )

        return ProjectDetailResponse(
            id=project.id,
            name=project.name,
            author_id=project.author_id,
            target_words=project.target_words,
            current_stage=project.current_stage,
            current_chapter=project.current_chapter,
            total_chapters=project.total_chapters,
            seed=project.seed,
            content_summary=content_summary,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def list_projects(self, user_id: int) -> list[Project]:
        """List all projects for a user."""
        result = await self.db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_project(
        self, project_id: int, user_id: int, data: ProjectUpdate
    ) -> Optional[Project]:
        """Update a project."""
        project = await self.get_project(project_id, user_id)
        if not project:
            return None

        if data.name is not None:
            project.name = data.name
        if data.seed is not None:
            project.seed = data.seed
        if data.target_words is not None:
            project.target_words = data.target_words

        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def delete_project(self, project_id: int, user_id: int) -> bool:
        """Delete a project."""
        project = await self.get_project(project_id, user_id)
        if not project:
            return False

        await self.db.delete(project)
        await self.db.flush()
        return True

    async def update_stage(
        self,
        project_id: int,
        stage: ProjectStage,
        current_chapter: Optional[int] = None,
        total_chapters: Optional[int] = None,
    ) -> None:
        """Update project stage and chapter info."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project:
            project.current_stage = stage
            if current_chapter is not None:
                project.current_chapter = current_chapter
            if total_chapters is not None:
                project.total_chapters = total_chapters
            await self.db.flush()

    # Content operations
    async def save_content(
        self, project_id: int, content_type: ContentType, content: str
    ) -> ProjectContent:
        """Save or update project content."""
        # Get current version
        result = await self.db.execute(
            select(ProjectContent)
            .where(
                ProjectContent.project_id == project_id,
                ProjectContent.content_type == content_type,
            )
            .order_by(ProjectContent.version.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        new_version = (existing.version + 1) if existing else 1

        new_content = ProjectContent(
            project_id=project_id,
            content_type=content_type,
            content=content,
            version=new_version,
        )
        self.db.add(new_content)
        await self.db.flush()
        await self.db.refresh(new_content)
        return new_content

    async def get_content(
        self, project_id: int, content_type: ContentType
    ) -> Optional[ProjectContent]:
        """Get latest content of a type."""
        result = await self.db.execute(
            select(ProjectContent)
            .where(
                ProjectContent.project_id == project_id,
                ProjectContent.content_type == content_type,
            )
            .order_by(ProjectContent.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # Blueprint operations
    async def save_blueprint(
        self, project_id: int, chapter_num: int, content: str
    ) -> Blueprint:
        """Save or update a blueprint."""
        result = await self.db.execute(
            select(Blueprint)
            .where(
                Blueprint.project_id == project_id,
                Blueprint.chapter_num == chapter_num,
            )
            .order_by(Blueprint.version.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        new_version = (existing.version + 1) if existing else 1

        blueprint = Blueprint(
            project_id=project_id,
            chapter_num=chapter_num,
            content=content,
            version=new_version,
        )
        self.db.add(blueprint)
        await self.db.flush()
        await self.db.refresh(blueprint)
        return blueprint

    async def get_blueprint(
        self, project_id: int, chapter_num: int
    ) -> Optional[Blueprint]:
        """Get latest blueprint for a chapter."""
        result = await self.db.execute(
            select(Blueprint)
            .where(
                Blueprint.project_id == project_id,
                Blueprint.chapter_num == chapter_num,
            )
            .order_by(Blueprint.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_blueprints(self, project_id: int) -> list[Blueprint]:
        """Get all blueprints for a project (latest version of each)."""
        # Subquery to get max version per chapter
        subq = (
            select(
                Blueprint.chapter_num,
                func.max(Blueprint.version).label("max_version"),
            )
            .where(Blueprint.project_id == project_id)
            .group_by(Blueprint.chapter_num)
            .subquery()
        )

        result = await self.db.execute(
            select(Blueprint)
            .join(
                subq,
                (Blueprint.chapter_num == subq.c.chapter_num)
                & (Blueprint.version == subq.c.max_version),
            )
            .where(Blueprint.project_id == project_id)
            .order_by(Blueprint.chapter_num)
        )
        return list(result.scalars().all())

    # Chapter operations
    async def save_chapter(
        self, project_id: int, chapter_num: int, content: str, word_count: int
    ) -> Chapter:
        """Save or update a chapter."""
        result = await self.db.execute(
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_num == chapter_num,
            )
            .order_by(Chapter.version.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        new_version = (existing.version + 1) if existing else 1

        chapter = Chapter(
            project_id=project_id,
            chapter_num=chapter_num,
            content=content,
            word_count=word_count,
            version=new_version,
        )
        self.db.add(chapter)
        await self.db.flush()
        await self.db.refresh(chapter)
        return chapter

    async def get_chapter(
        self, project_id: int, chapter_num: int
    ) -> Optional[Chapter]:
        """Get latest chapter."""
        result = await self.db.execute(
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_num == chapter_num,
            )
            .order_by(Chapter.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_chapters(self, project_id: int) -> list[Chapter]:
        """Get all chapters for a project (latest version of each)."""
        subq = (
            select(
                Chapter.chapter_num,
                func.max(Chapter.version).label("max_version"),
            )
            .where(Chapter.project_id == project_id)
            .group_by(Chapter.chapter_num)
            .subquery()
        )

        result = await self.db.execute(
            select(Chapter)
            .join(
                subq,
                (Chapter.chapter_num == subq.c.chapter_num)
                & (Chapter.version == subq.c.max_version),
            )
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_num)
        )
        return list(result.scalars().all())
