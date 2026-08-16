import uuid
import datetime
from sqlalchemy import String, Integer, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, UTCDateTime

class Repository(Base):
    """
    SQLAlchemy model representing a GitHub repository imported into CodeForge.
    Enforces a unique linkage per user/github_repo_id combination.
    """
    __tablename__ = "repositories"

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
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    github_repo_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    owner: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    default_branch: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    local_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="importing",  # importing, indexed, failed
        nullable=False
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    # JSON columns to store indexing outputs
    languages: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )
    frameworks: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    dependency_files: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    last_indexed_at: Mapped[datetime.datetime] = mapped_column(
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

    # Relationship back to the owner
    user = relationship("User", backref="repositories")
    jobs = relationship("AgentJob", back_populates="repository", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="repository", cascade="all, delete-orphan")

    # Table constraints to prevent duplicate imports of a repo by the same user
    __table_args__ = (
        UniqueConstraint("user_id", "github_repo_id", name="uq_user_github_repo"),
    )
