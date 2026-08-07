"""SQLAlchemy Storage Adapter - implements StoragePort using SQLAlchemy."""

import json
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
            .order_by(PipelineRunModel.id.desc())
            .limit(1)
        )
        model = result.scalars().first()
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
            .order_by(PipelineRunModel.id.desc())
            .limit(1)
        )
        run_model = run_result.scalars().first()
        if not run_model:
            raise ValueError(f"No pipeline run for project {project_id}")

        model = PhaseResultModel(
            pipeline_run_id=run_model.id,
            phase_name=result.phase.value,
            status=result.status,
            output_json=self._dump_json(result.output),
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

    @staticmethod
    def _load_json(raw: Optional[str]) -> Optional[dict]:
        """Deserialize a JSON text column, tolerating null/empty values."""
        if not raw:
            return None
        return json.loads(raw)

    @staticmethod
    def _dump_json(value: Optional[dict]) -> Optional[str]:
        """Serialize a dict to a JSON text column value (None stays NULL)."""
        if value is None:
            return None
        return json.dumps(value)

    def _project_to_domain(self, model: ProjectModel) -> DomainProject:
        """Convert ORM model to domain entity."""
        dna_data = self._load_json(model.story_dna_json)
        story_dna = None
        if dna_data:
            story_dna = StoryDNA(
                spark=dna_data.get("spark", {}),
                genre=dna_data.get("genre", {}),
                world=dna_data.get("world", {}),
                characters=dna_data.get("characters", {}),
                conflict=dna_data.get("conflict", {}),
                structure=dna_data.get("structure", {}),
                voice=dna_data.get("voice", {}),
            )

        # target_words has no dedicated column; derive it from the DNA structure.
        target_words = 50000
        if story_dna and isinstance(story_dna.structure, dict):
            target_words = story_dna.structure.get("target_words", target_words)

        return DomainProject(
            id=model.id,
            name=model.name,
            user_id=model.user_id,
            author_id=model.author_id or "",
            story_dna=story_dna,
            target_words=target_words,
            total_chapters=model.chapter_count or 10,
            created_at=model.created_at,
            topic_analysis=self._load_json(model.topic_analysis_json),
            thesis=self._load_json(model.story_thesis_json),
            character_system=self._load_json(model.character_system_json),
            architecture=self._load_json(model.story_architecture_json),
        )

    def _project_to_model(self, project: DomainProject) -> ProjectModel:
        """Convert domain entity to ORM model."""
        return ProjectModel(
            name=project.name,
            user_id=project.user_id,
            author_id=project.author_id,
            story_dna_json=self._dump_json(project.story_dna.to_dict() if project.story_dna else None),
            chapter_count=project.total_chapters,
        )

    def _update_project_model(
        self,
        model: ProjectModel,
        project: DomainProject
    ) -> None:
        """Update ORM model from domain entity."""
        model.name = project.name
        model.author_id = project.author_id
        model.story_dna_json = self._dump_json(project.story_dna.to_dict() if project.story_dna else None)
        model.chapter_count = project.total_chapters
        model.topic_analysis_json = self._dump_json(project.topic_analysis)
        model.story_thesis_json = self._dump_json(project.thesis)
        model.character_system_json = self._dump_json(project.character_system)
        model.story_architecture_json = self._dump_json(project.architecture)

    def _pipeline_run_to_domain(self, model: PipelineRunModel) -> DomainPipelineRun:
        """Convert ORM model to domain entity."""
        # auto_approve / estimated_cost_usd have no dedicated columns; they live
        # in the state_json blob.
        state = self._load_json(model.state_json) or {}
        return DomainPipelineRun(
            id=model.id,
            project_id=model.project_id,
            author_id=model.author_id,
            status=model.status,
            current_phase=PhaseType(model.current_phase) if model.current_phase else None,
            current_chapter=model.current_chapter or 0,
            auto_approve=state.get("auto_approve", False),
            total_input_tokens=model.total_input_tokens or 0,
            total_output_tokens=model.total_output_tokens or 0,
            estimated_cost_usd=state.get("estimated_cost_usd", 0.0),
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

    def _run_state_json(self, run: DomainPipelineRun) -> str:
        """Serialize the run fields that have no dedicated columns."""
        return self._dump_json({
            "auto_approve": run.auto_approve,
            "estimated_cost_usd": run.estimated_cost_usd,
        })

    def _pipeline_run_to_model(self, run: DomainPipelineRun) -> PipelineRunModel:
        """Convert domain entity to ORM model."""
        return PipelineRunModel(
            project_id=run.project_id,
            author_id=run.author_id,
            status=run.status,
            current_phase=run.current_phase.value if run.current_phase else None,
            current_chapter=run.current_chapter,
            total_input_tokens=run.total_input_tokens,
            total_output_tokens=run.total_output_tokens,
            state_json=self._run_state_json(run),
            started_at=run.started_at,
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
        model.state_json = self._run_state_json(run)
        if run.started_at:
            model.started_at = run.started_at
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
