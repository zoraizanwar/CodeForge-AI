"""
Database models for CodeForge AI agent tasks, executions, Git operations, and feedback repair iterations (Step 7, 8, 9, & 10).
"""
import uuid
import datetime
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, UTCDateTime


class AgentTask(Base):
    """
    SQLAlchemy model representing an AI Software Engineer Agent Task.
    Tracks user request, implementation plan, file context, generated code diffs, approval state, PR links, and repair feedback status.
    """
    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    task_description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # pending, analyzing, planning, generating, ready_for_review, approved, executing, execution_failed, repairing, repair_ready, execution_passed, pr_ready, pr_created, failed, human_review_required
        nullable=False,
        index=True
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    approved_patch_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=True
    )
    approved_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    plan: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )
    files_analyzed: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    files_to_modify: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    changes: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )

    # Relationships
    user = relationship("User", backref="agent_tasks")
    repository = relationship("Repository", backref="agent_tasks")
    executions = relationship("AgentExecution", backref="task", cascade="all, delete-orphan", order_by="AgentExecution.created_at.desc()")
    git_operations = relationship("GitOperation", backref="task", cascade="all, delete-orphan", order_by="GitOperation.created_at.desc()")
    iterations = relationship("AgentIteration", backref="task", cascade="all, delete-orphan", order_by="AgentIteration.iteration_number.asc()")
    jobs = relationship("AgentJob", back_populates="agent_task", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")


class AgentExecution(Base):
    """
    SQLAlchemy model representing an execution run of an agent task patch inside an isolated workspace (Step 8).
    """
    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # pending, preparing, applying, testing, passed, failed, cancelled
        nullable=False,
        index=True
    )
    workspace_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )
    command_results: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    test_summary: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )
    stdout: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False
    )
    stderr: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False
    )
    exit_code: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )


class GitOperation(Base):
    """
    SQLAlchemy model representing a Git & GitHub PR operation (Step 9).
    Tracks feature branch creation, patch commits, pushes, and GitHub Pull Requests.
    """
    __tablename__ = "git_operations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    operation_type: Mapped[str] = mapped_column(
        String(50),
        default="pull_request",  # branch, commit, push, pull_request
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # pending, preparing, applying, committing, pushing, creating_pr, completed, failed, cancelled
        nullable=False,
        index=True
    )
    branch_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=True
    )
    remote_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )
    pull_request_number: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    pull_request_url: Mapped[str] = mapped_column(
        String(512),
        nullable=True
    )
    commit_message: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    extra_metadata: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )

    # Relationships
    repository = relationship("Repository", backref="git_operations")
    user = relationship("User", backref="git_operations")
    execution = relationship("AgentExecution", backref="git_operations")


class AgentIteration(Base):
    """
    SQLAlchemy model representing an autonomous repair iteration attempt for an AgentTask (Step 10).
    Analyzes failed sandbox test executions, constructs root cause hypotheses, and applies validated repair patches.
    """
    __tablename__ = "agent_iterations"
    __table_args__ = (
        UniqueConstraint("task_id", "iteration_number", name="uq_agent_iteration_task_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    iteration_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    trigger_execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="analyzing",  # analyzing, planning, generating, validating, executing, passed, failed, stopped
        nullable=False,
        index=True
    )
    failure_category: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )
    failure_summary: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    root_cause: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    plan: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )
    patch_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    files_changed: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )

    # Relationships
    trigger_execution = relationship("AgentExecution", foreign_keys=[trigger_execution_id])
    execution = relationship("AgentExecution", foreign_keys=[execution_id])
