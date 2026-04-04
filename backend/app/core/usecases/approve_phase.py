"""
Approve Phase Use Case - handles phase approval/rejection.
"""

from dataclasses import dataclass
from typing import Optional

from ..domain import PipelineRun, PhaseType
from ..domain.values import PipelineStatus, PhaseStatus
from ..ports import StoragePort, EventPort


@dataclass
class ApprovePhaseRequest:
    """Request to approve or reject a phase."""
    project_id: int
    phase: str
    approved: bool
    rejection_reason: Optional[str] = None


@dataclass
class ApprovePhaseResult:
    """Result of approval action."""
    success: bool
    pipeline_run: Optional[PipelineRun] = None
    error: Optional[str] = None
    next_phase: Optional[str] = None


class ApprovePhaseUseCase:
    """
    Handles approval or rejection of pipeline phases.

    When approved, signals the pipeline to continue.
    When rejected, marks for regeneration.
    """

    def __init__(
        self,
        storage: StoragePort,
        events: EventPort,
    ):
        self.storage = storage
        self.events = events

    async def execute(
        self,
        request: ApprovePhaseRequest
    ) -> ApprovePhaseResult:
        """
        Process phase approval/rejection.

        Args:
            request: Approval request

        Returns:
            ApprovePhaseResult with status
        """
        # Get current pipeline run
        run = await self.storage.get_pipeline_run(request.project_id)
        if not run:
            return ApprovePhaseResult(
                success=False,
                error=f"No pipeline run found for project {request.project_id}"
            )

        # Verify we're awaiting approval
        if run.status != PipelineStatus.AWAITING_APPROVAL.value:
            return ApprovePhaseResult(
                success=False,
                error=f"Pipeline is not awaiting approval (status: {run.status})"
            )

        # Find the phase
        phase_result = None
        for p in run.phases:
            if p.phase.value == request.phase:
                phase_result = p
                break

        if not phase_result:
            return ApprovePhaseResult(
                success=False,
                error=f"Phase {request.phase} not found in pipeline run"
            )

        if request.approved:
            # Mark as approved and continue
            run.status = PipelineStatus.RUNNING.value

            # Determine next phase
            phases = list(PhaseType)
            current_index = phases.index(PhaseType(request.phase))
            next_phase = None
            if current_index < len(phases) - 1:
                next_phase = phases[current_index + 1].value

            await self.storage.save_pipeline_run(run)

            return ApprovePhaseResult(
                success=True,
                pipeline_run=run,
                next_phase=next_phase
            )

        else:
            # Mark for regeneration
            phase_result.status = PhaseStatus.PENDING.value
            phase_result.output = None
            phase_result.error = f"Rejected: {request.rejection_reason}"

            run.status = PipelineStatus.RUNNING.value

            await self.storage.save_pipeline_run(run)
            await self.events.emit_phase_started(
                request.project_id,
                request.phase
            )

            return ApprovePhaseResult(
                success=True,
                pipeline_run=run,
                next_phase=request.phase  # Regenerate same phase
            )
