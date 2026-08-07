"""Pipeline logger for streaming updates via WebSocket."""

import json
from datetime import datetime
from typing import Any, Optional

import redis

from app.config import get_settings

settings = get_settings()


class PipelineLogger:
    """Logger for streaming pipeline updates to WebSocket clients via Redis pub/sub."""

    def __init__(
        self,
        project_id: int,
        task_id: int,
        redis_client: Optional[redis.Redis] = None,
    ):
        self.project_id = project_id
        self.task_id = task_id
        self.redis = redis_client or redis.from_url(settings.redis_url)
        self.channel = f"project:{project_id}"

    def _publish(self, message_type: str, data: dict[str, Any]) -> None:
        """Publish a message to the project channel."""
        message = {
            "type": message_type,
            "task_id": self.task_id,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        }
        self.redis.publish(self.channel, json.dumps(message))

    def step(self, message: str, progress_percent: int) -> None:
        """Log a pipeline step with progress."""
        self._publish(
            "pipeline.step",
            {
                "message": message,
                "progress_percent": progress_percent,
            },
        )

    def thinking(self, thought: str) -> None:
        """Log AI thinking/reasoning process."""
        self._publish(
            "pipeline.thinking",
            {
                "thought": thought,
            },
        )

    def artifact(
        self,
        name: str,
        artifact_type: str,
        preview: str,
        full_content: Optional[str] = None,
    ) -> None:
        """Log a generated artifact."""
        self._publish(
            "pipeline.artifact",
            {
                "name": name,
                "artifact_type": artifact_type,
                "preview": preview[:500] if preview else "",
                "has_full_content": full_content is not None,
            },
        )

    def decision(self, decision: str, reasoning: str) -> None:
        """Log a decision with reasoning."""
        self._publish(
            "pipeline.decision",
            {
                "decision": decision,
                "reasoning": reasoning,
            },
        )

    def cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_eur: float,
        total_cost_eur: float,
    ) -> None:
        """Log cost update."""
        self._publish(
            "pipeline.cost",
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_eur": cost_eur,
                "total_cost_eur": total_cost_eur,
            },
        )

    def warning(self, message: str, action_required: bool = False) -> None:
        """Log a warning or pause notification."""
        self._publish(
            "pipeline.warning",
            {
                "message": message,
                "action_required": action_required,
            },
        )

    def progress(self, status: str, message: str, progress_percent: int) -> None:
        """Legacy progress update for compatibility."""
        self._publish(
            "generation.progress",
            {
                "status": status,
                "message": message,
                "progress_percent": progress_percent,
            },
        )

    def content_ready(self, content_preview: str, word_count: int) -> None:
        """Notify that content is ready for approval."""
        self._publish(
            "generation.content_ready",
            {
                "content_preview": content_preview[:500] if content_preview else "",
                "word_count": word_count,
            },
        )

    def completed(self, next_stage: Optional[str] = None) -> None:
        """Notify that the task is completed."""
        self._publish(
            "generation.completed",
            {
                "next_stage": next_stage,
            },
        )

    def error(self, error_message: str, recoverable: bool = True) -> None:
        """Log an error."""
        self._publish(
            "generation.error",
            {
                "error": error_message,
                "recoverable": recoverable,
            },
        )
