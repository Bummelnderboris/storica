"""Cost controller for tracking LLM costs and implementing pause/resume logic."""

import json
from typing import Optional, Tuple

import redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.cost import CostRecord
from app.tasks.pipeline_logger import PipelineLogger

settings = get_settings()


class CostController:
    """Controller for tracking and limiting LLM costs."""

    # Gemini pricing per million tokens (USD)
    PRICING = {
        "gemini-2.0-flash": {
            "input": settings.gemini_flash_input_price,
            "output": settings.gemini_flash_output_price,
        },
        "gemini-1.5-flash": {
            "input": 0.075,
            "output": 0.30,
        },
        "gemini-1.5-pro": {
            "input": settings.gemini_pro_input_price,
            "output": settings.gemini_pro_output_price,
        },
    }

    def __init__(
        self,
        project_id: int,
        task_id: int,
        user_id: int,
        db: Session,
        logger: Optional[PipelineLogger] = None,
        redis_client: Optional[redis.Redis] = None,
    ):
        self.project_id = project_id
        self.task_id = task_id
        self.user_id = user_id
        self.db = db
        self.logger = logger
        self.redis = redis_client or redis.from_url(settings.redis_url)
        self.running_cost_eur = 0.0

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "gemini-2.0-flash",
    ) -> Tuple[float, float]:
        """Calculate cost in USD and EUR for given token counts."""
        pricing = self.PRICING.get(model, self.PRICING["gemini-2.0-flash"])

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        cost_usd = input_cost + output_cost
        cost_eur = cost_usd * settings.usd_to_eur_rate

        return cost_usd, cost_eur

    def get_project_total_cost(self) -> float:
        """Get total cost for the project in EUR."""
        result = self.db.execute(
            select(func.coalesce(func.sum(CostRecord.cost_eur), 0.0)).where(
                CostRecord.project_id == self.project_id
            )
        )
        return float(result.scalar() or 0.0)

    def record_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "gemini-2.0-flash",
        stage: Optional[str] = None,
        chapter_num: Optional[int] = None,
    ) -> Tuple[float, float, bool]:
        """
        Record a cost entry and return (cost_eur, total_cost_eur, can_continue).

        Returns False for can_continue if cost limit is reached.
        """
        cost_usd, cost_eur = self.calculate_cost(input_tokens, output_tokens, model)
        self.running_cost_eur += cost_eur

        # Create cost record
        record = CostRecord(
            project_id=self.project_id,
            user_id=self.user_id,
            task_id=self.task_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            cost_eur=cost_eur,
            model=model,
            stage=stage,
            chapter_num=chapter_num,
        )
        self.db.add(record)
        self.db.commit()

        # Get total project cost
        total_cost = self.get_project_total_cost()

        # Log cost update
        if self.logger:
            self.logger.cost(input_tokens, output_tokens, cost_eur, total_cost)

        # Check if we should pause
        can_continue = True
        if total_cost >= settings.cost_limit_eur:
            can_continue = False
            if self.logger:
                self.logger.warning(
                    f"Kostenlimit von {settings.cost_limit_eur} EUR erreicht!",
                    action_required=True,
                )
        elif total_cost >= settings.cost_warning_eur:
            if self.logger:
                self.logger.warning(
                    f"Kosten nähern sich dem Limit: {total_cost:.2f}/{settings.cost_limit_eur:.2f} EUR"
                )

        return cost_eur, total_cost, can_continue

    def can_continue(self, additional_cost_eur: float = 0.0) -> bool:
        """Check if we can continue based on projected costs."""
        total = self.get_project_total_cost() + additional_cost_eur
        return total < settings.cost_limit_eur

    def request_user_confirmation(self) -> None:
        """Request user confirmation to continue past cost warning."""
        pause_key = f"cost_pause:{self.project_id}"
        self.redis.set(pause_key, "pending", ex=3600)  # 1 hour expiry

        if self.logger:
            self.logger.warning(
                f"Kostenlimit fast erreicht. Warten auf Bestätigung zum Fortfahren.",
                action_required=True,
            )

    def check_resume(self) -> bool:
        """Check if user has confirmed to resume."""
        pause_key = f"cost_pause:{self.project_id}"
        status = self.redis.get(pause_key)

        if status is None:
            return True  # No pause active
        if status == b"confirmed":
            self.redis.delete(pause_key)
            return True

        return False

    def confirm_resume(self, additional_budget_eur: float = 1.0) -> None:
        """User confirms to resume with additional budget."""
        pause_key = f"cost_pause:{self.project_id}"
        self.redis.set(pause_key, "confirmed")

        # Store new limit temporarily
        new_limit = self.get_project_total_cost() + additional_budget_eur
        self.redis.set(
            f"cost_temp_limit:{self.project_id}",
            str(new_limit),
            ex=3600,
        )
