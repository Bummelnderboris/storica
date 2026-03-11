"""Author endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.author import AuthorDetail, AuthorSummary
from app.services.author import AuthorService

router = APIRouter()


@router.get("", response_model=list[AuthorSummary])
async def list_authors():
    """List all available authors."""
    service = AuthorService()
    return service.list_authors()


@router.get("/{author_id}", response_model=AuthorDetail)
async def get_author(author_id: str):
    """Get detailed author profile."""
    service = AuthorService()
    author = service.get_author(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    return author
