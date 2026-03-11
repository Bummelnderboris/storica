"""Cost tracking schemas."""

from datetime import datetime

from pydantic import BaseModel


class CostRecord(BaseModel):
    """Schema for a single cost record."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime

    model_config = {"from_attributes": True}


class CostSummary(BaseModel):
    """Summary of costs for a user."""

    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    record_count: int


class ProjectCostResponse(BaseModel):
    """Cost summary for a specific project."""

    project_id: int
    project_name: str
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int


class UserCostResponse(BaseModel):
    """Cost summary across all projects for a user."""

    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    projects: list[ProjectCostResponse]
