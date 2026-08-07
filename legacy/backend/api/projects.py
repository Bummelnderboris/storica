"""Projects API endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import Project, Chapter, User
from .deps import get_current_active_user

router = APIRouter(prefix="/projects", tags=["projects"])


class StoryDNAInput(BaseModel):
    spark: dict
    genre: dict
    world: dict
    characters: dict
    conflict: dict
    structure: dict
    voice: dict


class ProjectCreate(BaseModel):
    name: str
    author_id: str
    story_dna: StoryDNAInput


class ProjectResponse(BaseModel):
    id: int
    name: str
    author_id: Optional[str]
    status: str
    total_words: int
    chapter_count: int
    estimated_cost: int

    class Config:
        from_attributes = True


class ChapterResponse(BaseModel):
    id: int
    chapter_number: int
    title: Optional[str]
    status: str
    word_count: int
    is_approved: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List user's projects."""
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    return projects


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new project with Story DNA."""
    project = Project(
        name=project_data.name,
        user_id=current_user.id,
        author_id=project_data.author_id,
        story_dna_json=json.dumps(project_data.story_dna.model_dump()),
        chapter_count=project_data.story_dna.structure.get("chapter_count", 12)
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a project by ID."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}


@router.get("/{project_id}/story-dna")
async def get_story_dna(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get project's Story DNA."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.story_dna_json:
        return json.loads(project.story_dna_json)
    return {}


@router.get("/{project_id}/chapters", response_model=List[ChapterResponse])
async def get_chapters(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get project chapters."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project.chapters


@router.get("/{project_id}/chapters/{chapter_number}")
async def get_chapter(
    project_id: int,
    chapter_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific chapter."""
    chapter = db.query(Chapter).join(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
        Chapter.chapter_number == chapter_number
    ).first()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return {
        "id": chapter.id,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "content": chapter.content,
        "status": chapter.status,
        "word_count": chapter.word_count,
        "is_approved": chapter.is_approved,
        "final_score": chapter.final_score / 10 if chapter.final_score else None
    }
