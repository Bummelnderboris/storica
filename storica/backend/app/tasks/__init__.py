"""Celery tasks for async generation."""

from app.tasks.celery_app import celery_app
from app.tasks.generation import (
    generate_essence_task,
    generate_architecture_task,
    generate_blueprint_task,
    generate_chapter_task,
)

__all__ = [
    "celery_app",
    "generate_essence_task",
    "generate_architecture_task",
    "generate_blueprint_task",
    "generate_chapter_task",
]
