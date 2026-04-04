"""WebSocket Events Adapter - implements EventPort using WebSockets."""

from typing import Any, Dict, Optional
import json

from ..core.ports.events import EventPort
from ..core.domain import PhaseResult, PipelineRun
from ..core.domain.values import CritiqueResult


class WebSocketEventAdapter(EventPort):
    """
    Event adapter using WebSocket connections.

    Broadcasts events to connected clients.
    """

    def __init__(self, connection_manager):
        """
        Initialize with connection manager.

        Args:
            connection_manager: WebSocket connection manager
        """
        self.manager = connection_manager

    async def emit_pipeline_started(
        self,
        project_id: int,
        run: PipelineRun
    ) -> None:
        """Emit pipeline started event."""
        await self._broadcast(project_id, {
            "type": "pipeline_started",
            "project_id": project_id,
            "author_id": run.author_id,
            "auto_approve": run.auto_approve,
        })

    async def emit_phase_started(
        self,
        project_id: int,
        phase: str
    ) -> None:
        """Emit phase started event."""
        await self._broadcast(project_id, {
            "type": "phase_started",
            "project_id": project_id,
            "phase": phase,
        })

    async def emit_phase_completed(
        self,
        project_id: int,
        result: PhaseResult
    ) -> None:
        """Emit phase completed event."""
        await self._broadcast(project_id, {
            "type": "phase_completed",
            "project_id": project_id,
            "phase": result.phase.value,
            "status": result.status,
            "execution_time_ms": result.execution_time_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        })

    async def emit_phase_failed(
        self,
        project_id: int,
        phase: str,
        error: str
    ) -> None:
        """Emit phase failed event."""
        await self._broadcast(project_id, {
            "type": "phase_failed",
            "project_id": project_id,
            "phase": phase,
            "error": error,
        })

    async def emit_approval_required(
        self,
        project_id: int,
        phase: str,
        preview: Dict[str, Any]
    ) -> None:
        """Emit approval required event."""
        await self._broadcast(project_id, {
            "type": "approval_required",
            "project_id": project_id,
            "phase": phase,
            "preview": preview,
        })

    async def emit_prose_chunk(
        self,
        project_id: int,
        chapter: int,
        chunk: str
    ) -> None:
        """Emit prose generation chunk (streaming)."""
        await self._broadcast(project_id, {
            "type": "prose_chunk",
            "project_id": project_id,
            "chapter": chapter,
            "chunk": chunk,
        })

    async def emit_critique_result(
        self,
        project_id: int,
        chapter: int,
        iteration: int,
        result: CritiqueResult
    ) -> None:
        """Emit critique result."""
        await self._broadcast(project_id, {
            "type": "critique_result",
            "project_id": project_id,
            "chapter": chapter,
            "iteration": iteration,
            "overall_score": result.overall_score,
            "passes_threshold": result.passes_threshold,
            "scores": [
                {"category": s.category, "score": s.score, "feedback": s.feedback}
                for s in result.scores
            ],
        })

    async def emit_pipeline_completed(
        self,
        project_id: int,
        run: PipelineRun
    ) -> None:
        """Emit pipeline completed event."""
        await self._broadcast(project_id, {
            "type": "pipeline_completed",
            "project_id": project_id,
            "total_input_tokens": run.total_input_tokens,
            "total_output_tokens": run.total_output_tokens,
            "estimated_cost_usd": run.estimated_cost_usd,
        })

    async def emit_error(
        self,
        project_id: int,
        error: str,
        phase: Optional[str] = None
    ) -> None:
        """Emit error event."""
        await self._broadcast(project_id, {
            "type": "error",
            "project_id": project_id,
            "phase": phase,
            "error": error,
        })

    async def _broadcast(self, project_id: int, data: Dict[str, Any]) -> None:
        """Broadcast message to project connections."""
        if self.manager:
            message = json.dumps(data)
            await self.manager.broadcast_to_project(project_id, message)
