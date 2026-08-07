"""Authors API endpoints."""

from fastapi import APIRouter, HTTPException
from typing import List

from ..authors import AuthorLoader

router = APIRouter(prefix="/authors", tags=["authors"])
author_loader = AuthorLoader()


@router.get("/")
async def list_authors() -> List[dict]:
    """List all available authors."""
    return author_loader.list_authors()


@router.get("/{author_id}")
async def get_author(author_id: str):
    """Get author profile."""
    try:
        profile = author_loader.load(author_id)
        return {
            "id": author_id,
            "name": profile.metadata.name,
            "language": profile.metadata.primary_language,
            "notable_works": profile.metadata.notable_works,
            "philosophy": profile.philosophy.worldview[:500],
            "themes": profile.themes.primary
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Author not found: {author_id}")


@router.get("/{author_id}/philosophy")
async def get_author_philosophy(author_id: str):
    """Get author philosophy summary."""
    try:
        return {"philosophy": author_loader.get_philosophy(author_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Author not found: {author_id}")


@router.get("/{author_id}/style-guide")
async def get_author_style_guide(author_id: str):
    """Get author style guide."""
    try:
        return {"style_guide": author_loader.get_style_guide(author_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Author not found: {author_id}")


@router.get("/{author_id}/critique-rubric")
async def get_author_critique_rubric(author_id: str):
    """Get author critique rubric."""
    try:
        return {"critique_rubric": author_loader.get_critique_rubric(author_id)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Author not found: {author_id}")
