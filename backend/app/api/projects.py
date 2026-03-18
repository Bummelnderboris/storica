"""Project endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.project import ContentType
from app.schemas.content import (
    BlueprintListResponse,
    BlueprintResponse,
    ChapterListResponse,
    ChapterResponse,
    ContentResponse,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.author import AuthorService
from app.services.project import ProjectService

router = APIRouter()


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: DbSession,
    current_user: CurrentUser,
):
    """List all projects for the current user."""
    service = ProjectService(db)
    projects = await service.list_projects(current_user.id)
    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=len(projects),
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new project."""
    # Validate author exists
    author_service = AuthorService()
    author = author_service.get_author(data.author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Author not found: {data.author_id}",
        )

    service = ProjectService(db)
    project = await service.create_project(current_user.id, data)
    return project


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get project details."""
    service = ProjectService(db)
    project = await service.get_project_with_details(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update a project."""
    service = ProjectService(db)
    project = await service.update_project(project_id, current_user.id, data)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Delete a project."""
    service = ProjectService(db)
    deleted = await service.delete_project(project_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )


# Content endpoints
@router.get("/{project_id}/essence", response_model=ContentResponse)
async def get_essence(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get project essence."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await service.get_content(project_id, ContentType.ESSENCE)
    if not content:
        raise HTTPException(status_code=404, detail="Essence not found")
    return content


@router.get("/{project_id}/architecture", response_model=ContentResponse)
async def get_architecture(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get project architecture."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await service.get_content(project_id, ContentType.ARCHITECTURE)
    if not content:
        raise HTTPException(status_code=404, detail="Architecture not found")
    return content


@router.get("/{project_id}/story-bible", response_model=ContentResponse)
async def get_story_bible(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get project story bible."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await service.get_content(project_id, ContentType.STORY_BIBLE)
    if not content:
        raise HTTPException(status_code=404, detail="Story bible not found")
    return content


# Blueprint endpoints
@router.get("/{project_id}/blueprints", response_model=BlueprintListResponse)
async def list_blueprints(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all blueprints for a project."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    blueprints = await service.get_all_blueprints(project_id)
    return BlueprintListResponse(
        blueprints=[BlueprintResponse.model_validate(b) for b in blueprints]
    )


@router.get("/{project_id}/blueprints/{chapter_num}", response_model=BlueprintResponse)
async def get_blueprint(
    project_id: int,
    chapter_num: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific blueprint."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    blueprint = await service.get_blueprint(project_id, chapter_num)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return blueprint


# Chapter endpoints
@router.get("/{project_id}/chapters", response_model=ChapterListResponse)
async def list_chapters(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all chapters for a project."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = await service.get_all_chapters(project_id)
    total_words = sum(c.word_count for c in chapters)
    return ChapterListResponse(
        chapters=[ChapterResponse.model_validate(c) for c in chapters],
        total_word_count=total_words,
    )


@router.get("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse)
async def get_chapter(
    project_id: int,
    chapter_num: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific chapter."""
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapter = await service.get_chapter(project_id, chapter_num)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter
