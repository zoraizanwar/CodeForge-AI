"""
AgentRun and AgentRunStep SQLAlchemy models for CodeForge AI Step 12 Multi-Agent Engineering Workflow.
Compatible with PostgreSQL (production) and SQLite (testing).
"""
import uuid
import datetime
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, UTCDateTime


class AgentRun(Base):
    """
    Represents an overarching multi-agent engineering workflow run.
    Orchestrates Planner, Engineer, Reviewer, Security Reviewer, Test Engineer, and Repair Agents.
    """
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=True)
    parent_job_id = Column(UUID(as_uuid=True), ForeignKey("agent_jobs.id", ondelete="SET NULL"), nullable=True)

    # Statuses: pending, running, reviewing, testing, repairing, approved, rejected, failed, completed, human_review_required, cancelled
    status = Column(String(50), nullable=False, default="pending")

    # Current active agent: planner, engineer, reviewer, tester, security, repair, orchestrator
    current_agent = Column(String(50), nullable=True, default="planner")

    workflow_stage = Column(String(100), nullable=False, default="pending")
    overall_progress = Column(Integer, nullable=False, default=0)

    final_decision = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    error_message = Column(Text, nullable=True)

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
    user = relationship("User", back_populates="agent_runs")
    repository = relationship("Repository", back_populates="agent_runs")
    task = relationship("AgentTask", back_populates="agent_runs")
    parent_job = relationship("AgentJob", backref="child_runs")
    steps = relationship("AgentRunStep", back_populates="run", cascade="all, delete-orphan", order_by="AgentRunStep.created_at.asc()")

    __table_args__ = (
        Index("ix_agent_runs_user_id", "user_id"),
        Index("ix_agent_runs_repository_id", "repository_id"),
        Index("ix_agent_runs_task_id", "task_id"),
        Index("ix_agent_runs_status", "status"),
        Index("ix_agent_runs_created_at", "created_at"),
        Index("ix_agent_runs_status_created_at", "status", "created_at"),
    )


class AgentRunStep(Base):
    """
    Represents an individual step executed by a specialized agent during a multi-agent run.
    """
    __tablename__ = "agent_run_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)

    # Agent types: planner, engineer, reviewer, tester, security, repair, orchestrator
    agent_type = Column(String(50), nullable=False)

    # Statuses: pending, running, passed, failed, review_needed, cancelled
    status = Column(String(50), nullable=False, default="pending")

    input_context = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    output = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    confidence = Column(Float, nullable=True)

    job_id = Column(UUID(as_uuid=True), ForeignKey("agent_jobs.id", ondelete="SET NULL"), nullable=True)

    started_at = Column(UTCDateTime, nullable=True)
    completed_at = Column(UTCDateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    # Relationships
    run = relationship("AgentRun", back_populates="steps")
    job = relationship("AgentJob")

    __table_args__ = (
        Index("ix_agent_run_steps_run_id", "run_id"),
        Index("ix_agent_run_steps_agent_type", "agent_type"),
        Index("ix_agent_run_steps_status", "status"),
        Index("ix_agent_run_steps_created_at", "created_at"),
    )
