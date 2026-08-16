"""
AuditEvent SQLAlchemy model for CodeForge AI Step 14 Production Observability & Audit Logging.
Compatible with PostgreSQL (production) and SQLite (testing).
"""
import uuid
import datetime
from sqlalchemy import Column, String, Boolean, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, UTCDateTime


class AuditEvent(Base):
    """
    Represents an immutable operational, security, agent, job, or system audit record.
    Tracks state changes, authentication, security violations, and workflow events safely.
    """
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("agent_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    # Event Details
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, default="info", index=True)  # info, warning, error, critical
    request_id = Column(String(128), nullable=True, index=True)
    success = Column(Boolean, nullable=False, default=True)

    # Bounded Safe Metadata Payload (JSON / JSONB)
    meta = Column("metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True)

    # Timestamps
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)

    # Relationships
    user = relationship("User", backref="audit_events", lazy="select")
    repository = relationship("Repository", backref="audit_events", lazy="select")
    agent_task = relationship("AgentTask", backref="audit_events", lazy="select")
    agent_run = relationship("AgentRun", backref="audit_events", lazy="select")
    job = relationship("AgentJob", backref="audit_events", lazy="select")

    __table_args__ = (
        Index("idx_audit_events_user_created", "user_id", "created_at"),
        Index("idx_audit_events_repo_created", "repository_id", "created_at"),
        Index("idx_audit_events_type_sev", "event_type", "severity"),
    )
