"""
SQLAlchemy models for repository intelligence (Step 6):
  - SourceFile    : scanned source code files
  - Symbol        : AST-extracted code symbols
  - CodeChunk     : semantic code chunks with optional vector embeddings
  - RepositoryAnalysis : high-level analysis metadata per repository
"""
import uuid
import datetime
from sqlalchemy import String, Integer, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator
from app.core.database import Base, UTCDateTime

try:
    from pgvector.sqlalchemy import Vector as PGVector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class HybridVector(TypeDecorator):
    """
    SQLAlchemy type decorator that resolves to pgvector Vector(1536) on
    PostgreSQL and to a plain JSON array on SQLite (unit tests).
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = 1536):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            return dialect.type_descriptor(PGVector(self.dimensions))
        return dialect.type_descriptor(JSON)


class SourceFile(Base):
    """Scanned source-code file record for a repository workspace."""
    __tablename__ = "source_files"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # SHA-256 hash of file contents — used for incremental indexing
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
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

    repository = relationship("Repository", backref="source_files")
    symbols: Mapped[list["Symbol"]] = relationship(
        "Symbol", back_populates="source_file", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["CodeChunk"]] = relationship(
        "CodeChunk", back_populates="source_file", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "path", name="uq_repo_file_path"),
    )


class Symbol(Base):
    """AST-extracted code symbol (class, function, method, route, import)."""
    __tablename__ = "symbols"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # type: "class" | "function" | "method" | "route" | "import"
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # JSON blob: args, decorators, return type, etc.
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON, name="metadata", nullable=True
    )

    source_file: Mapped["SourceFile"] = relationship(
        "SourceFile", back_populates="symbols"
    )
    chunks: Mapped[list["CodeChunk"]] = relationship(
        "CodeChunk", back_populates="symbol", cascade="all, delete-orphan"
    )


class CodeChunk(Base):
    """Semantic code text chunk with optional pgvector embedding."""
    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list | None] = mapped_column(
        HybridVector(1536), nullable=True
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    source_file: Mapped["SourceFile"] = relationship(
        "SourceFile", back_populates="chunks"
    )
    symbol: Mapped["Symbol | None"] = relationship(
        "Symbol", back_populates="chunks"
    )


class RepositoryAnalysis(Base):
    """High-level architectural analysis metadata for a repository."""
    __tablename__ = "repository_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )
    # status: "pending" | "processing" | "completed" | "failed"
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    architecture_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # e.g. ["app/main.py", "src/index.tsx"]
    entry_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # e.g. {"fastapi": "0.110", "react": "18.0"}
    dependencies_parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_analyzed_at: Mapped[datetime.datetime | None] = mapped_column(
        UTCDateTime, nullable=True
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

    repository = relationship("Repository", backref="analysis")
