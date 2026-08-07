"""Celery tasks for pipeline execution."""

import json
import asyncio
from typing import Optional
from celery import shared_task

from .celery_app import celery_app
from ..services.llm import get_llm_service
from ..prompts import PromptEngine
from ..authors import AuthorLoader
from ..orchestrator import PipelineOrchestrator, PipelineCallbacks


@celery_app.task(bind=True, name="pipeline.run")
def run_pipeline_task(
    self,
    project_id: int,
    author_id: str,
    story_dna: dict,
    auto_approve: bool = False
):
    """
    Main Celery task to run the generation pipeline.

    Args:
        project_id: Project ID
        author_id: Author profile ID
        story_dna: Story DNA from quiz
        auto_approve: Skip approval gates if True
    """
    # Create async event loop for running async code
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(
            _run_pipeline_async(
                self,
                project_id,
                author_id,
                story_dna,
                auto_approve
            )
        )
        return result
    finally:
        loop.close()


async def _run_pipeline_async(
    task,
    project_id: int,
    author_id: str,
    story_dna: dict,
    auto_approve: bool
):
    """Async pipeline execution."""

    # Initialize services
    llm = get_llm_service()
    prompts = PromptEngine()
    authors = AuthorLoader()

    # Create orchestrator
    orchestrator = PipelineOrchestrator(llm, prompts, authors)

    # Create callbacks for progress updates
    callbacks = PipelineCallbacks(
        on_phase_start=lambda phase: _emit_phase_start(task, project_id, phase),
        on_phase_complete=lambda phase, output: _emit_phase_complete(task, project_id, phase, output),
        on_approval_required=lambda phase, output: _emit_approval_required(task, project_id, phase, output),
        on_chapter_start=lambda ch: _emit_chapter_start(task, project_id, ch),
        on_chapter_complete=lambda ch: _emit_chapter_complete(task, project_id, ch),
        on_pipeline_complete=lambda state: _emit_pipeline_complete(task, project_id, state),
        on_error=lambda phase, error: _emit_error(task, project_id, phase, error)
    )

    # Run the pipeline
    state = await orchestrator.run_pipeline(
        project_id=project_id,
        author_id=author_id,
        story_dna=story_dna,
        callbacks=callbacks,
        auto_approve=auto_approve
    )

    return state.to_dict()


def _emit_phase_start(task, project_id: int, phase: str):
    """Emit phase start event."""
    task.update_state(
        state="PROGRESS",
        meta={
            "project_id": project_id,
            "event": "phase_start",
            "phase": phase
        }
    )
    # Also emit via WebSocket
    _send_ws_event(project_id, "phase_start", {"phase": phase})


def _emit_phase_complete(task, project_id: int, phase: str, output: dict):
    """Emit phase complete event."""
    task.update_state(
        state="PROGRESS",
        meta={
            "project_id": project_id,
            "event": "phase_complete",
            "phase": phase,
            "output_summary": _summarize_output(output)
        }
    )
    _send_ws_event(project_id, "phase_complete", {"phase": phase})


def _emit_approval_required(task, project_id: int, phase: str, output: dict):
    """Emit approval required event."""
    task.update_state(
        state="AWAITING_APPROVAL",
        meta={
            "project_id": project_id,
            "event": "approval_required",
            "phase": phase,
            "output_preview": _summarize_output(output)
        }
    )
    _send_ws_event(project_id, "approval_required", {
        "phase": phase,
        "output_preview": _summarize_output(output)
    })


def _emit_chapter_start(task, project_id: int, chapter: int):
    """Emit chapter start event."""
    task.update_state(
        state="PROGRESS",
        meta={
            "project_id": project_id,
            "event": "chapter_start",
            "chapter": chapter
        }
    )
    _send_ws_event(project_id, "chapter_start", {"chapter": chapter})


def _emit_chapter_complete(task, project_id: int, chapter: int):
    """Emit chapter complete event."""
    task.update_state(
        state="PROGRESS",
        meta={
            "project_id": project_id,
            "event": "chapter_complete",
            "chapter": chapter
        }
    )
    _send_ws_event(project_id, "chapter_complete", {"chapter": chapter})


def _emit_pipeline_complete(task, project_id: int, state: dict):
    """Emit pipeline complete event."""
    _send_ws_event(project_id, "pipeline_complete", {
        "status": state.get("status"),
        "cost": state.get("cost")
    })


def _emit_error(task, project_id: int, phase: str, error: str):
    """Emit error event."""
    task.update_state(
        state="FAILURE",
        meta={
            "project_id": project_id,
            "event": "error",
            "phase": phase,
            "error": error
        }
    )
    _send_ws_event(project_id, "error", {"phase": phase, "error": error})


def _summarize_output(output: dict) -> dict:
    """Create a summary of output for events."""
    summary = {}

    for key, value in output.items():
        if isinstance(value, str):
            summary[key] = value[:200] + "..." if len(value) > 200 else value
        elif isinstance(value, list):
            summary[key] = f"[{len(value)} items]"
        elif isinstance(value, dict):
            summary[key] = f"{{...{len(value)} keys}}"
        else:
            summary[key] = value

    return summary


def _send_ws_event(project_id: int, event_type: str, data: dict):
    """Send event via WebSocket (stub - implement with actual WS)."""
    # This would publish to Redis pubsub for WebSocket distribution
    # For now, just log
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"WS Event [{project_id}] {event_type}: {data}")


@celery_app.task(name="pipeline.approve_phase")
def approve_phase_task(project_id: int, phase: str):
    """Handle phase approval."""
    # This would signal the waiting pipeline task
    pass


@celery_app.task(name="pipeline.reject_phase")
def reject_phase_task(project_id: int, phase: str, reason: str):
    """Handle phase rejection."""
    pass


@celery_app.task(name="pipeline.cancel")
def cancel_pipeline_task(project_id: int):
    """Cancel a running pipeline."""
    pass
