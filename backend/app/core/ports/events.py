"""Events Port - interface for event broadcasting."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..domain import PhaseResult, PipelineRun
from ..domain.values import CritiqueResult


class EventPort(ABC):
    """Abstract interface for event broadcasting."""

    @abstractmethod
    async def emit_pipeline_started(
        self,
        project_id: int,
        run: PipelineRun
    ) -> None:
        """Emit pipeline started event."""
        pass

    @abstractmethod
    async def emit_phase_started(
        self,
        project_id: int,
        phase: str
    ) -> None:
        """Emit phase started event."""
        pass

    @abstractmethod
    async def emit_phase_completed(
        self,
        project_id: int,
        result: PhaseResult
    ) -> None:
        """Emit phase completed event."""
        pass

    @abstractmethod
    async def emit_phase_failed(
        self,
        project_id: int,
        phase: str,
        error: str
    ) -> None:
        """Emit phase failed event."""
        pass

    @abstractmethod
    async def emit_approval_required(
        self,
        project_id: int,
        phase: str,
        preview: Dict[str, Any]
    ) -> None:
        """Emit approval required event."""
        pass

    @abstractmethod
    async def emit_prose_chunk(
        self,
        project_id: int,
        chapter: int,
        chunk: str
    ) -> None:
        """Emit prose generation chunk (streaming)."""
        pass

    @abstractmethod
    async def emit_critique_result(
        self,
        project_id: int,
        chapter: int,
        iteration: int,
        result: CritiqueResult
    ) -> None:
        """Emit critique result."""
        pass

    @abstractmethod
    async def emit_pipeline_completed(
        self,
        project_id: int,
        run: PipelineRun
    ) -> None:
        """Emit pipeline completed event."""
        pass

    @abstractmethod
    async def emit_error(
        self,
        project_id: int,
        error: str,
        phase: Optional[str] = None
    ) -> None:
        """Emit error event."""
        pass
