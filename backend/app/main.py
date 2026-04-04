"""Storica Backend - Novel Generation API."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api import auth, projects, authors, websocket, pipeline
from .api.websocket import manager as ws_manager
from .container import get_container


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup and teardown."""
    # Setup: Initialize container with connection manager
    container = get_container()
    container.set_connection_manager(ws_manager)

    yield

    # Teardown: Clean up resources
    pass


app = FastAPI(
    title="Storica API",
    description="Novel generation with author style emulation",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth.router)       # /auth/*
app.include_router(projects.router)   # /projects/*
app.include_router(authors.router)    # /authors/*
app.include_router(pipeline.router)   # /pipeline/* - THE entry point for generation
app.include_router(websocket.router)  # /ws/*


@app.get("/")
async def root():
    """API info."""
    return {
        "service": "storica-api",
        "version": "2.0.0",
        "endpoints": {
            "auth": "/auth/login, /auth/register",
            "projects": "/projects/",
            "authors": "/authors/",
            "pipeline": "/pipeline/projects/{id}/start",
            "websocket": "/ws/projects/{id}",
        },
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}
