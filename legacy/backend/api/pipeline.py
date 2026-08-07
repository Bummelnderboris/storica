"""
Pipeline API - Story generation endpoints.

This is THE entry point for story generation.
Uses the core use cases with proper dependency injection.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_async_db, AsyncSessionLocal
from ..container import get_container
from ..core.usecases.generate_story import GenerateStoryRequest
from ..core.usecases.approve_phase import ApprovePhaseRequest
from ..core.domain.values import GenerationConfig, PipelineStatus

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# === Request/Response Models ===

class StartPipelineRequest(BaseModel):
    """Request to start story generation."""
    author_id: str
    auto_approve: bool = False


class PhaseInfo(BaseModel):
    """Information about a pipeline phase."""
    phase_name: str
    status: str
    execution_time_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    """Pipeline status response."""
    project_id: int
    status: str
    current_phase: Optional[str] = None
    current_chapter: int = 0
    total_chapters: int = 0
    progress_percent: float = 0.0
    phases: List[PhaseInfo] = []
    cost: Dict[str, Any] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PhaseApprovalRequest(BaseModel):
    """Request to approve or reject a phase."""
    approved: bool
    rejection_reason: Optional[str] = None


# === Background Task ===

async def run_generation_background(project_id: int, author_id: str, auto_approve: bool):
    """Run generation in background."""
    async with AsyncSessionLocal() as session:
        container = get_container()
        usecase = container.get_generate_story_usecase(session)

        config = GenerationConfig(auto_approve=auto_approve)
        request = GenerateStoryRequest(
            project_id=project_id,
            author_id=author_id,
            config=config,
        )

        await usecase.execute(request)


# === Endpoints ===

@router.post("/projects/{project_id}/start")
async def start_pipeline(
    project_id: int,
    request: StartPipelineRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_db),
):
    """
    Start story generation for a project.

    Pipeline phases:
    1. author_loading - Load author profile
    2. topic_exploration - Analyze story concept
    3. thesis_development - Develop central thesis
    4. character_derivation - Create characters
    5. story_architecture - Design structure
    6. blueprint_planning - Plan chapters
    7. prose_generation - Write chapters (with critique loop)
    8. consistency_check - Verify consistency
    """
    container = get_container()

    # Verify author exists
    author = await container.authors.get_author(request.author_id)
    if not author:
        raise HTTPException(
            status_code=404,
            detail=f"Author '{request.author_id}' not found. Available: duerrenmatt, hemingway"
        )

    # Start in background
    background_tasks.add_task(
        run_generation_background,
        project_id,
        request.author_id,
        request.auto_approve,
    )

    return {
        "success": True,
        "message": f"Pipeline started with author '{author.name}'",
        "project_id": project_id,
    }


@router.get("/projects/{project_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    project_id: int,
    session: AsyncSession = Depends(get_async_db),
):
    """Get current pipeline status."""
    from ..adapters import SQLAlchemyStorageAdapter

    storage = SQLAlchemyStorageAdapter(session)
    run = await storage.get_pipeline_run(project_id)

    if not run:
        return PipelineStatusResponse(project_id=project_id, status="idle")

    phases = [
        PhaseInfo(
            phase_name=p.phase.value,
            status=p.status,
            execution_time_ms=p.execution_time_ms,
            input_tokens=p.input_tokens,
            output_tokens=p.output_tokens,
            error=p.error,
        )
        for p in run.phases
    ]

    return PipelineStatusResponse(
        project_id=project_id,
        status=run.status,
        current_phase=run.current_phase.value if run.current_phase else None,
        current_chapter=run.current_chapter,
        progress_percent=run.progress_percent,
        phases=phases,
        cost={
            "input_tokens": run.total_input_tokens,
            "output_tokens": run.total_output_tokens,
            "estimated_cost_usd": run.estimated_cost_usd,
        },
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/projects/{project_id}/pause")
async def pause_pipeline(
    project_id: int,
    session: AsyncSession = Depends(get_async_db),
):
    """Pause the pipeline at the next checkpoint."""
    from ..adapters import SQLAlchemyStorageAdapter

    storage = SQLAlchemyStorageAdapter(session)
    run = await storage.get_pipeline_run(project_id)

    if not run:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    if run.status != PipelineStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail=f"Pipeline is {run.status}, not running")

    run.status = PipelineStatus.PAUSED.value
    await storage.save_pipeline_run(run)

    return {"success": True, "message": "Pipeline paused"}


@router.post("/projects/{project_id}/resume")
async def resume_pipeline(
    project_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_db),
):
    """Resume a paused pipeline."""
    from ..adapters import SQLAlchemyStorageAdapter

    storage = SQLAlchemyStorageAdapter(session)
    run = await storage.get_pipeline_run(project_id)

    if not run:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    if run.status not in [PipelineStatus.PAUSED.value, PipelineStatus.AWAITING_APPROVAL.value]:
        raise HTTPException(status_code=400, detail=f"Pipeline is {run.status}, cannot resume")

    background_tasks.add_task(
        run_generation_background,
        project_id,
        run.author_id,
        run.auto_approve,
    )

    return {"success": True, "message": "Pipeline resumed"}


@router.get("/projects/{project_id}/phases/{phase}/preview")
async def get_phase_preview(
    project_id: int,
    phase: str,
    session: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get preview of phase output for approval."""
    from ..adapters import SQLAlchemyStorageAdapter

    storage = SQLAlchemyStorageAdapter(session)
    run = await storage.get_pipeline_run(project_id)

    if not run:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    for p in run.phases:
        if p.phase.value == phase:
            return {"phase": phase, "status": p.status, "output": p.output or {}}

    raise HTTPException(status_code=404, detail=f"Phase '{phase}' not found")


@router.post("/projects/{project_id}/phases/{phase}/approve")
async def approve_phase(
    project_id: int,
    phase: str,
    request: PhaseApprovalRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_db),
):
    """Approve or reject a phase."""
    container = get_container()
    usecase = container.get_approve_phase_usecase(session)

    approval_request = ApprovePhaseRequest(
        project_id=project_id,
        phase=phase,
        approved=request.approved,
        rejection_reason=request.rejection_reason,
    )

    result = await usecase.execute(approval_request)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    # Continue pipeline if approved
    if request.approved and result.pipeline_run:
        background_tasks.add_task(
            run_generation_background,
            project_id,
            result.pipeline_run.author_id,
            result.pipeline_run.auto_approve,
        )

    return {
        "success": True,
        "approved": request.approved,
        "next_phase": result.next_phase,
    }


@router.get("/projects/{project_id}/artifacts/{artifact_type}")
async def get_artifact(
    project_id: int,
    artifact_type: str,
    chapter: Optional[int] = None,
    session: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get a generated artifact."""
    from ..adapters import SQLAlchemyStorageAdapter

    storage = SQLAlchemyStorageAdapter(session)
    project = await storage.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    artifact_map = {
        "topic_analysis": project.topic_analysis,
        "thesis": project.thesis,
        "characters": project.character_system,
        "architecture": project.architecture,
    }

    if artifact_type in artifact_map:
        return {"type": artifact_type, "content": artifact_map[artifact_type] or {}}

    if artifact_type == "chapter":
        if chapter is None:
            chapters = await storage.list_chapters(project_id)
            return {"type": "chapters", "content": [{"number": c.number, "title": c.title} for c in chapters]}
        ch = await storage.get_chapter(project_id, chapter)
        if not ch:
            raise HTTPException(status_code=404, detail=f"Chapter {chapter} not found")
        return {"type": "chapter", "content": {"number": ch.number, "title": ch.title, "text": ch.content}}

    if artifact_type == "story_bible":
        bible = await storage.get_story_bible(project_id)
        return {"type": "story_bible", "content": bible.to_context_string() if bible else ""}

    raise HTTPException(status_code=400, detail=f"Unknown artifact: {artifact_type}")


@router.get("/projects/{project_id}/pending-approvals")
async def get_pending_approvals(
    project_id: int,
    session: AsyncSession = Depends(get_async_db),
):
    """Get pending approvals for a project."""
    from ..adapters import SQLAlchemyStorageAdapter

    storage = SQLAlchemyStorageAdapter(session)
    run = await storage.get_pipeline_run(project_id)

    if not run or run.status != PipelineStatus.AWAITING_APPROVAL.value:
        return {"pending": []}

    pending = []
    if run.current_phase:
        for p in run.phases:
            if p.phase == run.current_phase and p.status == "completed":
                pending.append({
                    "phase": p.phase.value,
                    "output_preview": p.output,
                })

    return {"pending": pending}
