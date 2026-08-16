"""create_agent_jobs_table

Revision ID: 2240dd64a7ba
Revises: 8d91af772e45
Create Date: 2026-08-16 08:36:03.223425

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import app.core.database

# revision identifiers, used by Alembic.
revision: str = '2240dd64a7ba'
down_revision: Union[str, None] = '8d91af772e45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=True),
    sa.Column('job_type', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('current_stage', sa.String(length=100), nullable=False),
    sa.Column('attempt_count', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('started_at', app.core.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('completed_at', app.core.database.UTCDateTime(timezone=True), nullable=True),
    sa.Column('created_at', app.core.database.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.core.database.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_jobs_created_at', 'agent_jobs', ['created_at'], unique=False)
    op.create_index('ix_agent_jobs_job_type', 'agent_jobs', ['job_type'], unique=False)
    op.create_index('ix_agent_jobs_repository_id', 'agent_jobs', ['repository_id'], unique=False)
    op.create_index('ix_agent_jobs_status', 'agent_jobs', ['status'], unique=False)
    op.create_index('ix_agent_jobs_status_created_at', 'agent_jobs', ['status', 'created_at'], unique=False)
    op.create_index('ix_agent_jobs_task_id', 'agent_jobs', ['task_id'], unique=False)
    op.create_index('ix_agent_jobs_user_id', 'agent_jobs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_agent_jobs_user_id', table_name='agent_jobs')
    op.drop_index('ix_agent_jobs_task_id', table_name='agent_jobs')
    op.drop_index('ix_agent_jobs_status_created_at', table_name='agent_jobs')
    op.drop_index('ix_agent_jobs_status', table_name='agent_jobs')
    op.drop_index('ix_agent_jobs_repository_id', table_name='agent_jobs')
    op.drop_index('ix_agent_jobs_job_type', table_name='agent_jobs')
    op.drop_index('ix_agent_jobs_created_at', table_name='agent_jobs')
    op.drop_table('agent_jobs')
