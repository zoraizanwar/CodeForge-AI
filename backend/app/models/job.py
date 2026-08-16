"""
AgentJob SQLAlchemy model for CodeForge AI Step 11 durable job orchestration system.
Compatible with PostgreSQL (production) and SQLite (testing).
"""
import uuid
import datetime
from sqlalchemy import Column, String, Integer, Text, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, UTCDateTime


class AgentJob(Base):
    """
    Represents a durable, persistent long-running asynchronous job.
    Survives worker/API restarts and supports retries, cancellation, and progress tracking.
    """
    __tablename__ = "agent_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True)

    # Job specifications: analysis, agent_task, execution, repair, pull_request
    job_type = Column(String(50), nullable=False)

    # Job status: queued, running, cancelling, cancelled, completed, failed, retrying
    status = Column(String(50), nullable=False, default="queued")

    # Progress & stage tracking
    progress = Column(Integer, nullable=False, default=0)
    current_stage = Column(String(100), nullable=False, default="queued")

    # Retry metadata
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    priority = Column(Integer, nullable=False, default=0)

    # Execution payloads & results (JSON compatible with SQLite tests and PostgreSQL JSONB)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    result = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    error_message = Column(Text, nullable=True)

    # Worker leases & heartbeats (Step 20)
    worker_id = Column(String(100), nullable=True)
    last_heartbeat = Column(UTCDateTime, nullable=True)
    lease_expires_at = Column(UTCDateTime, nullable=True)


    # Timestamps
    started_at = Column(UTCDateTime, nullable=True)
    completed_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    # Relationships
    user = relationship("User", back_populates="jobs")
    repository = relationship("Repository", back_populates="jobs")
    agent_task = relationship("AgentTask", back_populates="jobs")

    __table_args__ = (
        Index("ix_agent_jobs_user_id", "user_id"),
        Index("ix_agent_jobs_repository_id", "repository_id"),
        Index("ix_agent_jobs_task_id", "task_id"),
        Index("ix_agent_jobs_status", "status"),
        Index("ix_agent_jobs_job_type", "job_type"),
        Index("ix_agent_jobs_created_at", "created_at"),
        Index("ix_agent_jobs_status_created_at", "status", "created_at"),
    )
