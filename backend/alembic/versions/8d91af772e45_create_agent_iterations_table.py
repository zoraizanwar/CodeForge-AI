"""create_agent_iterations_table

Revision ID: 8d91af772e45
Revises: 7c90ae881f34
Create Date: 2026-08-16 08:25:30.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d91af772e45'
down_revision: Union[str, None] = '7c90ae881f34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_iterations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('iteration_number', sa.Integer(), nullable=False),
        sa.Column('trigger_execution_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='analyzing'),
        sa.Column('failure_category', sa.String(length=50), nullable=True),
        sa.Column('failure_summary', sa.Text(), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('plan', sa.JSON(), nullable=True),
        sa.Column('patch_hash', sa.String(length=128), nullable=True),
        sa.Column('execution_id', sa.UUID(), nullable=True),
        sa.Column('files_changed', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trigger_execution_id'], ['agent_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execution_id'], ['agent_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'iteration_number', name='uq_agent_iteration_task_number')
    )
    op.create_index(op.f('ix_agent_iterations_id'), 'agent_iterations', ['id'], unique=False)
    op.create_index(op.f('ix_agent_iterations_task_id'), 'agent_iterations', ['task_id'], unique=False)
    op.create_index(op.f('ix_agent_iterations_trigger_execution_id'), 'agent_iterations', ['trigger_execution_id'], unique=False)
    op.create_index(op.f('ix_agent_iterations_execution_id'), 'agent_iterations', ['execution_id'], unique=False)
    op.create_index(op.f('ix_agent_iterations_status'), 'agent_iterations', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_iterations_status'), table_name='agent_iterations')
    op.drop_index(op.f('ix_agent_iterations_execution_id'), table_name='agent_iterations')
    op.drop_index(op.f('ix_agent_iterations_trigger_execution_id'), table_name='agent_iterations')
    op.drop_index(op.f('ix_agent_iterations_task_id'), table_name='agent_iterations')
    op.drop_index(op.f('ix_agent_iterations_id'), table_name='agent_iterations')
    op.drop_table('agent_iterations')
