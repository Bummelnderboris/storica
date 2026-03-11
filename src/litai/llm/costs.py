"""Cost tracking for LLM usage."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json


# Pricing per 1M tokens (as of early 2024, approximate)
MODEL_PRICING = {
    "gemini-1.5-flash": {
        "input": 0.075,  # $0.075 per 1M input tokens
        "output": 0.30,  # $0.30 per 1M output tokens
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "output": 5.00,
    },
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40,
    },
}


@dataclass
class UsageRecord:
    """A single usage record."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class CostTracker:
    """Tracks LLM usage and costs."""

    project_name: Optional[str] = None
    records: list[UsageRecord] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    def track(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "gemini-1.5-flash",
    ) -> None:
        """Track a generation call."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gemini-1.5-flash"])

        cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

        self.records.append(record)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

    def get_summary(self) -> dict:
        """Get usage summary."""
        return {
            "project": self.project_name,
            "total_calls": len(self.records),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
        }

    def save(self, path: Path) -> None:
        """Save cost data to file."""
        data = {
            "summary": self.get_summary(),
            "records": [
                {
                    "timestamp": r.timestamp,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": r.cost_usd,
                }
                for r in self.records
            ],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path, project_name: Optional[str] = None) -> "CostTracker":
        """Load cost data from file."""
        tracker = cls(project_name=project_name)

        if not path.exists():
            return tracker

        with open(path) as f:
            data = json.load(f)

        for record in data.get("records", []):
            tracker.records.append(UsageRecord(**record))
            tracker.total_input_tokens += record["input_tokens"]
            tracker.total_output_tokens += record["output_tokens"]
            tracker.total_cost_usd += record["cost_usd"]

        return tracker
