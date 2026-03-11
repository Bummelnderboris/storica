"""API routes."""

from fastapi import APIRouter

from app.api import auth, projects, generation, authors, websocket

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(generation.router, prefix="/generation", tags=["generation"])
api_router.include_router(authors.router, prefix="/authors", tags=["authors"])
api_router.include_router(websocket.router, tags=["websocket"])
