"""Approval gates for pipeline phases."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from enum import Enum


class ApprovalDecision(str, Enum):
    """Decision made at an approval gate."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    """A request for approval at a gate."""
    gate_id: str
    phase_name: str
    project_id: int
    output_preview: dict
    created_at: datetime = field(default_factory=datetime.utcnow)
    decision: ApprovalDecision = ApprovalDecision.PENDING
    decided_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class ApprovalGate:
    """
    Manages approval gates for pipeline phases.

    Allows async waiting for user approval before continuing.
    """

    def __init__(self, timeout_seconds: int = 3600):  # 1 hour default
        self.timeout = timeout_seconds
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._events: Dict[str, asyncio.Event] = {}
        self._callbacks: Dict[str, Callable] = {}

    def create_gate(
        self,
        phase_name: str,
        project_id: int,
        output_preview: dict
    ) -> str:
        """
        Create a new approval gate.

        Returns:
            gate_id for tracking
        """
        gate_id = f"{project_id}_{phase_name}_{datetime.utcnow().timestamp()}"

        request = ApprovalRequest(
            gate_id=gate_id,
            phase_name=phase_name,
            project_id=project_id,
            output_preview=output_preview
        )

        self._pending_requests[gate_id] = request
        self._events[gate_id] = asyncio.Event()

        return gate_id

    async def wait_for_approval(
        self,
        gate_id: str,
        on_waiting: Optional[Callable] = None
    ) -> ApprovalRequest:
        """
        Wait for approval at a gate.

        Args:
            gate_id: The gate to wait at
            on_waiting: Optional callback when waiting starts

        Returns:
            The approval request with decision
        """
        if gate_id not in self._pending_requests:
            raise ValueError(f"Unknown gate: {gate_id}")

        if on_waiting:
            on_waiting(self._pending_requests[gate_id])

        event = self._events[gate_id]

        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            request = self._pending_requests[gate_id]
            request.decision = ApprovalDecision.TIMEOUT
            request.decided_at = datetime.utcnow()

        return self._pending_requests[gate_id]

    def approve(self, gate_id: str) -> bool:
        """
        Approve a pending request.

        Returns:
            True if approval was recorded
        """
        if gate_id not in self._pending_requests:
            return False

        request = self._pending_requests[gate_id]
        request.decision = ApprovalDecision.APPROVED
        request.decided_at = datetime.utcnow()

        if gate_id in self._events:
            self._events[gate_id].set()

        return True

    def reject(self, gate_id: str, reason: str = "") -> bool:
        """
        Reject a pending request.

        Returns:
            True if rejection was recorded
        """
        if gate_id not in self._pending_requests:
            return False

        request = self._pending_requests[gate_id]
        request.decision = ApprovalDecision.REJECTED
        request.decided_at = datetime.utcnow()
        request.rejection_reason = reason

        if gate_id in self._events:
            self._events[gate_id].set()

        return True

    def get_pending(self, project_id: Optional[int] = None) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = [
            r for r in self._pending_requests.values()
            if r.decision == ApprovalDecision.PENDING
        ]

        if project_id is not None:
            pending = [r for r in pending if r.project_id == project_id]

        return pending

    def get_request(self, gate_id: str) -> Optional[ApprovalRequest]:
        """Get a specific request."""
        return self._pending_requests.get(gate_id)

    def cleanup(self, gate_id: str) -> None:
        """Clean up a gate after processing."""
        self._pending_requests.pop(gate_id, None)
        self._events.pop(gate_id, None)
        self._callbacks.pop(gate_id, None)

    def cleanup_project(self, project_id: int) -> None:
        """Clean up all gates for a project."""
        to_remove = [
            gid for gid, req in self._pending_requests.items()
            if req.project_id == project_id
        ]
        for gate_id in to_remove:
            self.cleanup(gate_id)
