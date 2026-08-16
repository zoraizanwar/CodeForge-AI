"""
Database models for CodeForge AI Step 20: Disaster Recovery, System Health Snapshots, and Backup Management.
"""
import uuid
import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Text, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, UTCDateTime


class RecoveryEvent(Base):
    """
    Tracks operational recovery actions, stale job reinstatements, lease expirations,
    and system repair events across tenant resources.
    """
    __tablename__ = "recovery_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    event_type = Column(String(100), nullable=False, index=True)  # e.g., job_recovery, stale_lease_relinquished, workspace_cleanup, database_reconnect
    resource_type = Column(String(50), nullable=False)  # e.g., agent_job, workspace, database, backup
    resource_id = Column(String(255), nullable=True)
    
    status = Column(String(50), nullable=False, default="completed")  # completed, failed, in_progress
    details = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)

    organization = relationship("Organization", backref="recovery_events")
    user = relationship("User", backref="recovery_events")


class SystemHealthSnapshot(Base):
    """
    Records system component health, disaster recovery readiness scores,
    and infrastructure status over time.
    """
    __tablename__ = "system_health_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    overall_status = Column(String(50), nullable=False, index=True)  # ready, degraded, failed
    database_status = Column(String(50), nullable=False)
    migrations_status = Column(String(50), nullable=False)
    job_queue_status = Column(String(50), nullable=False)
    workers_status = Column(String(50), nullable=False)
    workspace_status = Column(String(50), nullable=False)
    backup_status = Column(String(50), nullable=False)
    storage_status = Column(String(50), nullable=False)
    pgvector_status = Column(String(50), nullable=False)
    
    metrics_summary = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    active_warnings = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)


class BackupRecord(Base):
    """
    Tracks automated database and workspace backups, metadata, checksums,
    and verification status (without storing raw secrets or credentials).
    """
    __tablename__ = "backup_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    backup_type = Column(String(50), nullable=False, default="database")  # database, workspace, full
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    checksum_sha256 = Column(String(64), nullable=False)
    
    status = Column(String(50), nullable=False, default="completed")  # in_progress, completed, failed, deleted
    is_verified = Column(Boolean, nullable=False, default=False)
    verified_at = Column(UTCDateTime, nullable=True)
    verification_details = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    
    expires_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)

    organization = relationship("Organization", backref="backup_records")
    created_by_user = relationship("User", backref="created_backups")
