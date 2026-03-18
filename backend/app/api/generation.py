"""Generation endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.generation import GenerationTask, TaskStatus, TaskType
from app.schemas.generation import (
    GenerationApproval,
    GenerationRegenerate,
    GenerationTaskCreate,
    GenerationTaskResponse,
)
from app.services.project import ProjectService
from app.tasks.generation import (
    generate_architecture_task,
    generate_blueprint_task,
    generate_chapter_task,
    generate_essence_task,
)
from sqlalchemy import select

router = APIRouter()


async def _verify_project_access(
    db, project_id: int, user_id: int
) -> None:
    """Verify user has access to project."""
    service = ProjectService(db)
    project = await service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )


async def _create_task(
    db,
    project_id: int,
    task_type: TaskType,
    chapter_num: Optional[int] = None,
    guidance: Optional[str] = None,
) -> GenerationTask:
    """Create a generation task."""
    task = GenerationTask(
        project_id=project_id,
        task_type=task_type,
        chapter_num=chapter_num,
        guidance=guidance,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


def _task_to_response(task: GenerationTask) -> GenerationTaskResponse:
    """Convert task to response schema."""
    result_preview = None
    if task.result:
        result_preview = task.result[:500] + "..." if len(task.result) > 500 else task.result

    return GenerationTaskResponse(
        id=task.id,
        project_id=task.project_id,
        task_type=task.task_type,
        chapter_num=task.chapter_num,
        status=task.status,
        progress_percent=task.progress_percent,
        progress_message=task.progress_message,
        result_preview=result_preview,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# Generation endpoints
@router.post("/projects/{project_id}/generate/essence", response_model=GenerationTaskResponse)
async def start_essence_generation(
    project_id: int,
    data: GenerationTaskCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Start essence generation."""
    await _verify_project_access(db, project_id, current_user.id)

    task = await _create_task(
        db, project_id, TaskType.ESSENCE, guidance=data.guidance
    )

    # Queue Celery task
    celery_task = generate_essence_task.delay(task.id)
    task.celery_task_id = celery_task.id
    task.status = TaskStatus.RUNNING
    await db.flush()

    return _task_to_response(task)


@router.post("/projects/{project_id}/generate/architecture", response_model=GenerationTaskResponse)
async def start_architecture_generation(
    project_id: int,
    data: GenerationTaskCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Start architecture generation."""
    await _verify_project_access(db, project_id, current_user.id)

    task = await _create_task(
        db, project_id, TaskType.ARCHITECTURE, guidance=data.guidance
    )

    celery_task = generate_architecture_task.delay(task.id)
    task.celery_task_id = celery_task.id
    task.status = TaskStatus.RUNNING
    await db.flush()

    return _task_to_response(task)


@router.post("/projects/{project_id}/generate/blueprint/{chapter_num}", response_model=GenerationTaskResponse)
async def start_blueprint_generation(
    project_id: int,
    chapter_num: int,
    data: GenerationTaskCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Start blueprint generation for a chapter."""
    await _verify_project_access(db, project_id, current_user.id)

    task = await _create_task(
        db, project_id, TaskType.BLUEPRINT, chapter_num=chapter_num, guidance=data.guidance
    )

    celery_task = generate_blueprint_task.delay(task.id)
    task.celery_task_id = celery_task.id
    task.status = TaskStatus.RUNNING
    await db.flush()

    return _task_to_response(task)


@router.post("/projects/{project_id}/generate/chapter/{chapter_num}", response_model=GenerationTaskResponse)
async def start_chapter_generation(
    project_id: int,
    chapter_num: int,
    data: GenerationTaskCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Start chapter prose generation."""
    await _verify_project_access(db, project_id, current_user.id)

    task = await _create_task(
        db, project_id, TaskType.CHAPTER, chapter_num=chapter_num, guidance=data.guidance
    )

    celery_task = generate_chapter_task.delay(task.id)
    task.celery_task_id = celery_task.id
    task.status = TaskStatus.RUNNING
    await db.flush()

    return _task_to_response(task)


# Task management endpoints
@router.get("/tasks/{task_id}", response_model=GenerationTaskResponse)
async def get_task_status(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get the status of a generation task."""
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify access
    await _verify_project_access(db, task.project_id, current_user.id)

    return _task_to_response(task)


@router.post("/tasks/{task_id}/approve", response_model=GenerationTaskResponse)
async def approve_task(
    task_id: int,
    data: GenerationApproval,
    db: DbSession,
    current_user: CurrentUser,
):
    """Approve generated content."""
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await _verify_project_access(db, task.project_id, current_user.id)

    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not awaiting approval (current status: {task.status})",
        )

    if data.approved:
        task.status = TaskStatus.APPROVED
        # Content is already saved; mark as completed
        task.status = TaskStatus.COMPLETED
    else:
        # User rejected - they need to regenerate with guidance
        pass

    await db.flush()
    return _task_to_response(task)


@router.post("/tasks/{task_id}/regenerate", response_model=GenerationTaskResponse)
async def regenerate_task(
    task_id: int,
    data: GenerationRegenerate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Regenerate content with guidance."""
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await _verify_project_access(db, task.project_id, current_user.id)

    # Create new task with guidance
    new_task = await _create_task(
        db,
        task.project_id,
        task.task_type,
        chapter_num=task.chapter_num,
        guidance=data.guidance,
    )

    # Queue appropriate Celery task
    if task.task_type == TaskType.ESSENCE:
        celery_task = generate_essence_task.delay(new_task.id)
    elif task.task_type == TaskType.ARCHITECTURE:
        celery_task = generate_architecture_task.delay(new_task.id)
    elif task.task_type == TaskType.BLUEPRINT:
        celery_task = generate_blueprint_task.delay(new_task.id)
    else:
        celery_task = generate_chapter_task.delay(new_task.id)

    new_task.celery_task_id = celery_task.id
    new_task.status = TaskStatus.RUNNING
    await db.flush()

    return _task_to_response(new_task)


@router.get("/projects/{project_id}/tasks", response_model=list[GenerationTaskResponse])
async def list_project_tasks(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all tasks for a project."""
    await _verify_project_access(db, project_id, current_user.id)

    result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.project_id == project_id)
        .order_by(GenerationTask.created_at.desc())
    )
    tasks = result.scalars().all()

    return [_task_to_response(t) for t in tasks]
