"""SQLAlchemy Storage Adapter - implements StoragePort using SQLAlchemy."""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.ports.storage import StoragePort
from ..core.domain import (
    Project as DomainProject,
    PipelineRun as DomainPipelineRun,
    PhaseResult as DomainPhaseResult,
    StoryBible as DomainStoryBible,
    Chapter as DomainChapter,
    StoryDNA,
    PhaseType,
)
from ..models import (
    Project as ProjectModel,
    Chapter as ChapterModel,
    PipelineRun as PipelineRunModel,
    PhaseResult as PhaseResultModel,
    StoryBible as StoryBibleModel,
)


class SQLAlchemyStorageAdapter(StoragePort):
    """
    Storage adapter using SQLAlchemy for persistence.

    Maps between domain entities and ORM models.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    # Project operations

    async def get_project(self, project_id: int) -> Optional[DomainProject]:
        """Get a project by ID."""
        result = await self.session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._project_to_domain(model)

    async def save_project(self, project: DomainProject) -> DomainProject:
        """Save/update a project."""
        if project.id:
            result = await self.session.execute(
                select(ProjectModel).where(ProjectModel.id == project.id)
            )
            model = result.scalar_one_or_none()
            if model:
                self._update_project_model(model, project)
            else:
                model = self._project_to_model(project)
                self.session.add(model)
        else:
            model = self._project_to_model(project)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)
        return self._project_to_domain(model)

    async def list_projects(self, user_id: int) -> List[DomainProject]:
        """List all projects for a user."""
        result = await self.session.execute(
            select(ProjectModel).where(ProjectModel.user_id == user_id)
        )
        models = result.scalars().all()
        return [self._project_to_domain(m) for m in models]

    # Pipeline run operations

    async def get_pipeline_run(self, project_id: int) -> Optional[DomainPipelineRun]:
        """Get the current pipeline run for a project."""
        result = await self.session.execute(
            select(PipelineRunModel)
            .where(PipelineRunModel.project_id == project_id)
            .order_by(PipelineRunModel.started_at.desc())
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._pipeline_run_to_domain(model)

    async def save_pipeline_run(self, run: DomainPipelineRun) -> DomainPipelineRun:
        """Save/update a pipeline run."""
        if run.id:
            result = await self.session.execute(
                select(PipelineRunModel).where(PipelineRunModel.id == run.id)
            )
            model = result.scalar_one_or_none()
            if model:
                self._update_pipeline_run_model(model, run)
            else:
                model = self._pipeline_run_to_model(run)
                self.session.add(model)
        else:
            model = self._pipeline_run_to_model(run)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)
        return self._pipeline_run_to_domain(model)

    async def save_phase_result(
        self,
        project_id: int,
        result: DomainPhaseResult
    ) -> DomainPhaseResult:
        """Save a phase result."""
        # Get current run
        run_result = await self.session.execute(
            select(PipelineRunModel)
            .where(PipelineRunModel.project_id == project_id)
            .order_by(PipelineRunModel.started_at.desc())
        )
        run_model = run_result.scalar_one_or_none()
        if not run_model:
            raise ValueError(f"No pipeline run for project {project_id}")

        model = PhaseResultModel(
            pipeline_run_id=run_model.id,
            phase_name=result.phase.value,
            status=result.status,
            output=result.output,
            error=result.error,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            execution_time_ms=result.execution_time_ms,
        )
        self.session.add(model)
        await self.session.commit()
        return result

    # Chapter operations

    async def get_chapter(
        self,
        project_id: int,
        chapter_number: int
    ) -> Optional[DomainChapter]:
        """Get a specific chapter."""
        result = await self.session.execute(
            select(ChapterModel)
            .where(ChapterModel.project_id == project_id)
            .where(ChapterModel.chapter_number == chapter_number)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._chapter_to_domain(model)

    async def save_chapter(
        self,
        project_id: int,
        chapter: DomainChapter
    ) -> DomainChapter:
        """Save/update a chapter."""
        result = await self.session.execute(
            select(ChapterModel)
            .where(ChapterModel.project_id == project_id)
            .where(ChapterModel.chapter_number == chapter.number)
        )
        model = result.scalar_one_or_none()

        if model:
            model.title = chapter.title
            model.content = chapter.content
            model.word_count = chapter.word_count
            model.status = chapter.status
        else:
            model = ChapterModel(
                project_id=project_id,
                chapter_number=chapter.number,
                title=chapter.title,
                content=chapter.content,
                word_count=chapter.word_count,
                status=chapter.status,
            )
            self.session.add(model)

        await self.session.commit()
        return chapter

    async def list_chapters(self, project_id: int) -> List[DomainChapter]:
        """List all chapters for a project."""
        result = await self.session.execute(
            select(ChapterModel)
            .where(ChapterModel.project_id == project_id)
            .order_by(ChapterModel.chapter_number)
        )
        models = result.scalars().all()
        return [self._chapter_to_domain(m) for m in models]

    # Story Bible operations

    async def get_story_bible(self, project_id: int) -> Optional[DomainStoryBible]:
        """Get the story bible for a project."""
        result = await self.session.execute(
            select(StoryBibleModel).where(StoryBibleModel.project_id == project_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return DomainStoryBible(
            project_id=model.project_id,
            entries=[],  # Would deserialize from JSON
            timeline=model.timeline or [],
            last_updated=model.updated_at,
        )

    async def save_story_bible(self, bible: DomainStoryBible) -> DomainStoryBible:
        """Save/update the story bible."""
        result = await self.session.execute(
            select(StoryBibleModel).where(StoryBibleModel.project_id == bible.project_id)
        )
        model = result.scalar_one_or_none()

        entries_data = [
            {
                "category": e.category,
                "name": e.name,
                "description": e.description,
                "first_appearance": e.first_appearance,
                "attributes": e.attributes,
            }
            for e in bible.entries
        ]

        if model:
            model.entries = entries_data
            model.timeline = bible.timeline
        else:
            model = StoryBibleModel(
                project_id=bible.project_id,
                entries=entries_data,
                timeline=bible.timeline,
            )
            self.session.add(model)

        await self.session.commit()
        return bible

    # Mapping helpers

    def _project_to_domain(self, model: ProjectModel) -> DomainProject:
        """Convert ORM model to domain entity."""
        story_dna = None
        if model.story_dna:
            story_dna = StoryDNA(
                spark=model.story_dna.get("spark", {}),
                genre=model.story_dna.get("genre", {}),
                world=model.story_dna.get("world", {}),
                characters=model.story_dna.get("characters", {}),
                conflict=model.story_dna.get("conflict", {}),
                structure=model.story_dna.get("structure", {}),
                voice=model.story_dna.get("voice", {}),
            )

        return DomainProject(
            id=model.id,
            name=model.name,
            user_id=model.user_id,
            author_id=model.author_id or "",
            story_dna=story_dna,
            target_words=model.target_words or 50000,
            total_chapters=model.total_chapters or 10,
            created_at=model.created_at,
            topic_analysis=model.topic_analysis,
            thesis=model.story_thesis,
            character_system=model.character_system,
            architecture=model.story_architecture,
        )

    def _project_to_model(self, project: DomainProject) -> ProjectModel:
        """Convert domain entity to ORM model."""
        return ProjectModel(
            name=project.name,
            user_id=project.user_id,
            author_id=project.author_id,
            story_dna=project.story_dna.to_dict() if project.story_dna else None,
            target_words=project.target_words,
            total_chapters=project.total_chapters,
        )

    def _update_project_model(
        self,
        model: ProjectModel,
        project: DomainProject
    ) -> None:
        """Update ORM model from domain entity."""
        model.name = project.name
        model.author_id = project.author_id
        model.story_dna = project.story_dna.to_dict() if project.story_dna else None
        model.target_words = project.target_words
        model.total_chapters = project.total_chapters
        model.topic_analysis = project.topic_analysis
        model.story_thesis = project.thesis
        model.character_system = project.character_system
        model.story_architecture = project.architecture

    def _pipeline_run_to_domain(self, model: PipelineRunModel) -> DomainPipelineRun:
        """Convert ORM model to domain entity."""
        return DomainPipelineRun(
            id=model.id,
            project_id=model.project_id,
            author_id=model.author_id,
            status=model.status,
            current_phase=PhaseType(model.current_phase) if model.current_phase else None,
            current_chapter=model.current_chapter or 0,
            auto_approve=model.auto_approve,
            total_input_tokens=model.total_input_tokens,
            total_output_tokens=model.total_output_tokens,
            estimated_cost_usd=model.estimated_cost_usd,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

    def _pipeline_run_to_model(self, run: DomainPipelineRun) -> PipelineRunModel:
        """Convert domain entity to ORM model."""
        return PipelineRunModel(
            project_id=run.project_id,
            author_id=run.author_id,
            status=run.status,
            current_phase=run.current_phase.value if run.current_phase else None,
            current_chapter=run.current_chapter,
            auto_approve=run.auto_approve,
            total_input_tokens=run.total_input_tokens,
            total_output_tokens=run.total_output_tokens,
            estimated_cost_usd=run.estimated_cost_usd,
        )

    def _update_pipeline_run_model(
        self,
        model: PipelineRunModel,
        run: DomainPipelineRun
    ) -> None:
        """Update ORM model from domain entity."""
        model.status = run.status
        model.current_phase = run.current_phase.value if run.current_phase else None
        model.current_chapter = run.current_chapter
        model.total_input_tokens = run.total_input_tokens
        model.total_output_tokens = run.total_output_tokens
        model.estimated_cost_usd = run.estimated_cost_usd
        model.completed_at = run.completed_at

    def _chapter_to_domain(self, model: ChapterModel) -> DomainChapter:
        """Convert ORM model to domain entity."""
        return DomainChapter(
            number=model.chapter_number,
            title=model.title,
            content=model.content,
            word_count=model.word_count or 0,
            status=model.status or "pending",
        )
