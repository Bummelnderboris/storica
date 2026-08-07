"""Pipeline rewrite migration.

Revision ID: 003_pipeline
Revises: 002_add_cost_fields
Create Date: 2026-03-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '003_pipeline'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pipeline_runs table
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='not_started'),
        sa.Column('current_phase', sa.String(100), nullable=True),
        sa.Column('author_id', sa.String(100), nullable=True),
        sa.Column('author_language', sa.String(10), nullable=True),
        sa.Column('current_chapter', sa.Integer(), default=0),
        sa.Column('total_chapters', sa.Integer(), default=0),
        sa.Column('total_input_tokens', sa.Integer(), default=0),
        sa.Column('total_output_tokens', sa.Integer(), default=0),
        sa.Column('state_json', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE')
    )
    op.create_index('ix_pipeline_runs_project_id', 'pipeline_runs', ['project_id'])
    op.create_index('ix_pipeline_runs_status', 'pipeline_runs', ['status'])

    # Create phase_results table
    op.create_table(
        'phase_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pipeline_run_id', sa.Integer(), nullable=False),
        sa.Column('phase_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('output_json', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), default=0),
        sa.Column('output_tokens', sa.Integer(), default=0),
        sa.Column('execution_time_ms', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['pipeline_run_id'], ['pipeline_runs.id'], ondelete='CASCADE'
        )
    )
    op.create_index('ix_phase_results_pipeline_run_id', 'phase_results', ['pipeline_run_id'])
    op.create_index('ix_phase_results_phase_name', 'phase_results', ['phase_name'])

    # Create story_bibles table
    op.create_table(
        'story_bibles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('bible_json', sa.Text(), nullable=False, default='{}'),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('last_chapter_updated', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE')
    )
    op.create_index('ix_story_bibles_project_id', 'story_bibles', ['project_id'])

    # Add new columns to projects table
    op.add_column('projects', sa.Column('story_dna_json', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('topic_analysis_json', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('story_thesis_json', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('character_system_json', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('story_architecture_json', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove columns from projects
    op.drop_column('projects', 'story_architecture_json')
    op.drop_column('projects', 'character_system_json')
    op.drop_column('projects', 'story_thesis_json')
    op.drop_column('projects', 'topic_analysis_json')
    op.drop_column('projects', 'story_dna_json')

    # Drop tables
    op.drop_index('ix_story_bibles_project_id', 'story_bibles')
    op.drop_table('story_bibles')

    op.drop_index('ix_phase_results_phase_name', 'phase_results')
    op.drop_index('ix_phase_results_pipeline_run_id', 'phase_results')
    op.drop_table('phase_results')

    op.drop_index('ix_pipeline_runs_status', 'pipeline_runs')
    op.drop_index('ix_pipeline_runs_project_id', 'pipeline_runs')
    op.drop_table('pipeline_runs')
