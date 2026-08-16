"""create_git_operations_table

Revision ID: 7c90ae881f34
Revises: 6b89fd770e23
Create Date: 2026-08-16 08:16:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c90ae881f34'
down_revision: Union[str, None] = '6b89fd770e23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add approval columns to agent_tasks
    op.add_column('agent_tasks', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('agent_tasks', sa.Column('approved_patch_hash', sa.String(length=128), nullable=True))
    op.add_column('agent_tasks', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))

    # Create git_operations table
    op.create_table(
        'git_operations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False, server_default='pull_request'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('remote_branch', sa.String(length=255), nullable=True),
        sa.Column('pull_request_number', sa.Integer(), nullable=True),
        sa.Column('pull_request_url', sa.String(length=512), nullable=True),
        sa.Column('commit_message', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execution_id'], ['agent_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_git_operations_id'), 'git_operations', ['id'], unique=False)
    op.create_index(op.f('ix_git_operations_repository_id'), 'git_operations', ['repository_id'], unique=False)
    op.create_index(op.f('ix_git_operations_task_id'), 'git_operations', ['task_id'], unique=False)
    op.create_index(op.f('ix_git_operations_execution_id'), 'git_operations', ['execution_id'], unique=False)
    op.create_index(op.f('ix_git_operations_user_id'), 'git_operations', ['user_id'], unique=False)
    op.create_index(op.f('ix_git_operations_status'), 'git_operations', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_git_operations_status'), table_name='git_operations')
    op.drop_index(op.f('ix_git_operations_user_id'), table_name='git_operations')
    op.drop_index(op.f('ix_git_operations_execution_id'), table_name='git_operations')
    op.drop_index(op.f('ix_git_operations_task_id'), table_name='git_operations')
    op.drop_index(op.f('ix_git_operations_repository_id'), table_name='git_operations')
    op.drop_index(op.f('ix_git_operations_id'), table_name='git_operations')
    op.drop_table('git_operations')
    op.drop_column('agent_tasks', 'approved_at')
    op.drop_column('agent_tasks', 'approved_patch_hash')
    op.drop_column('agent_tasks', 'is_approved')
