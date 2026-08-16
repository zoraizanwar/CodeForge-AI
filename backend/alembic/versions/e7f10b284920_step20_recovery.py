"""step20_recovery

Revision ID: e7f10b284920
Revises: bc051daf4c17
Create Date: 2026-08-16 23:14:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import app
from sqlalchemy.dialects import postgresql

revision: str = 'e7f10b284920'
down_revision: Union[str, None] = 'bc051daf4c17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add worker lease columns to agent_jobs
    op.add_column('agent_jobs', sa.Column('worker_id', sa.String(length=100), nullable=True))
    op.add_column('agent_jobs', sa.Column('last_heartbeat', app.core.database.UTCDateTime(timezone=True), nullable=True))
    op.add_column('agent_jobs', sa.Column('lease_expires_at', app.core.database.UTCDateTime(timezone=True), nullable=True))

    # 2. Create recovery_events table
    op.create_table('recovery_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', app.core.database.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_events_created_at'), 'recovery_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_recovery_events_event_type'), 'recovery_events', ['event_type'], unique=False)

    # 3. Create system_health_snapshots table
    op.create_table('system_health_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('overall_status', sa.String(length=50), nullable=False),
        sa.Column('database_status', sa.String(length=50), nullable=False),
        sa.Column('migrations_status', sa.String(length=50), nullable=False),
        sa.Column('job_queue_status', sa.String(length=50), nullable=False),
        sa.Column('workers_status', sa.String(length=50), nullable=False),
        sa.Column('workspace_status', sa.String(length=50), nullable=False),
        sa.Column('backup_status', sa.String(length=50), nullable=False),
        sa.Column('storage_status', sa.String(length=50), nullable=False),
        sa.Column('pgvector_status', sa.String(length=50), nullable=False),
        sa.Column('metrics_summary', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('active_warnings', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('created_at', app.core.database.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_health_snapshots_created_at'), 'system_health_snapshots', ['created_at'], unique=False)
    op.create_index(op.f('ix_system_health_snapshots_overall_status'), 'system_health_snapshots', ['overall_status'], unique=False)

    # 4. Create backup_records table
    op.create_table('backup_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('backup_type', sa.String(length=50), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('file_path', sa.String(length=1024), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('verified_at', app.core.database.UTCDateTime(timezone=True), nullable=True),
        sa.Column('verification_details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('expires_at', app.core.database.UTCDateTime(timezone=True), nullable=True),
        sa.Column('created_at', app.core.database.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backup_records_created_at'), 'backup_records', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_backup_records_created_at'), table_name='backup_records')
    op.drop_table('backup_records')
    op.drop_index(op.f('ix_system_health_snapshots_overall_status'), table_name='system_health_snapshots')
    op.drop_index(op.f('ix_system_health_snapshots_created_at'), table_name='system_health_snapshots')
    op.drop_table('system_health_snapshots')
    op.drop_index(op.f('ix_recovery_events_event_type'), table_name='recovery_events')
    op.drop_index(op.f('ix_recovery_events_created_at'), table_name='recovery_events')
    op.drop_table('recovery_events')
    op.drop_column('agent_jobs', 'lease_expires_at')
    op.drop_column('agent_jobs', 'last_heartbeat')
    op.drop_column('agent_jobs', 'worker_id')
