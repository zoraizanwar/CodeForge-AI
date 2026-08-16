import uuid
import datetime
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, UTCDateTime

class GitHubInstallation(Base):
    """
    SQLAlchemy model representing a GitHub App installation linked to a CodeForge User.
    Enforces a one-to-one relationship per user.
    """
    __tablename__ = "github_installations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,  # Restricts each user to one active installation relationship
        nullable=False,
        index=True
    )
    installation_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        index=True,
        nullable=False
    )
    github_account_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    github_account_login: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    github_account_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
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
    user = relationship("User", backref="github_installation")

class OAuthState(Base):
    """
    SQLAlchemy model representing OAuth state keys stored securely.
    Saves a SHA-256 hash of the generated tokens, tied to user contexts.
    """
    __tablename__ = "oauth_states"

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
    state_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=False
    )
    used_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )

    # Relationships
    user = relationship("User", backref="oauth_states")
