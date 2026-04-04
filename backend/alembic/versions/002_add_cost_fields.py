"""Add cost tracking fields.

Revision ID: 002
Revises: 001
Create Date: 2024-03-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to cost_records
    op.add_column(
        "cost_records",
        sa.Column("task_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "cost_records",
        sa.Column("cost_eur", sa.Float(), nullable=True, server_default="0.0")
    )
    op.add_column(
        "cost_records",
        sa.Column("stage", sa.String(50), nullable=True)
    )
    op.add_column(
        "cost_records",
        sa.Column("chapter_num", sa.Integer(), nullable=True)
    )

    # Add foreign key for task_id
    op.create_foreign_key(
        "fk_cost_records_task_id",
        "cost_records",
        "generation_tasks",
        ["task_id"],
        ["id"],
        ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_cost_records_task_id", "cost_records", type_="foreignkey")
    op.drop_column("cost_records", "chapter_num")
    op.drop_column("cost_records", "stage")
    op.drop_column("cost_records", "cost_eur")
    op.drop_column("cost_records", "task_id")
