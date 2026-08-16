"""add_knowledge_and_vector_tables

Revision ID: 3656ec558b46
Revises: 4bd9b2537f39
Create Date: 2026-08-16 05:01:26.663138

NOTE: pgvector (CREATE EXTENSION vector) must be installed on the PostgreSQL
server before running this migration. If pgvector is not available, the
embedding column falls back to TEXT (storing JSON-serialized arrays).
Run this SQL manually as a superuser to install the extension:
    CREATE EXTENSION IF NOT EXISTS vector;
Then rerun: alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3656ec558b46'
down_revision: Union[str, None] = '4bd9b2537f39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_pgvector(bind) -> bool:
    """Check if the pgvector extension is available on the server."""
    try:
        result = bind.execute(sa.text(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def _pgvector_enabled(bind) -> bool:
    """Check if pgvector extension is already enabled in the current DB."""
    try:
        result = bind.execute(sa.text(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # ── Enable pgvector if available ────────────────────────────────────
    pgvector_active = False
    if is_pg:
        if _has_pgvector(bind):
            if not _pgvector_enabled(bind):
                bind.execute(sa.text("CREATE EXTENSION vector"))
            pgvector_active = True
        else:
            import warnings
            warnings.warn(
                "pgvector extension is NOT installed on this PostgreSQL server. "
                "The embedding column will use TEXT. Install pgvector and run "
                "'alembic downgrade -1 && alembic upgrade head' to enable it.",
                stacklevel=2
            )

    # ── repository_analyses ─────────────────────────────────────────────
    op.create_table(
        'repository_analyses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('repository_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('architecture_summary', sa.Text(), nullable=True),
        sa.Column('entry_points', sa.JSON(), nullable=True),
        sa.Column('dependencies_parsed', sa.JSON(), nullable=True),
        sa.Column('last_analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repository_analyses_id', 'repository_analyses', ['id'])
    op.create_index('ix_repository_analyses_repository_id', 'repository_analyses', ['repository_id'], unique=True)

    # ── source_files ────────────────────────────────────────────────────
    op.create_table(
        'source_files',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('repository_id', sa.Uuid(), nullable=False),
        sa.Column('path', sa.String(length=512), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'path', name='uq_repo_file_path'),
    )
    op.create_index('ix_source_files_id', 'source_files', ['id'])
    op.create_index('ix_source_files_repository_id', 'source_files', ['repository_id'])

    # ── symbols ─────────────────────────────────────────────────────────
    op.create_table(
        'symbols',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_file_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('end_line_number', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['source_file_id'], ['source_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_symbols_id', 'symbols', ['id'])
    op.create_index('ix_symbols_name', 'symbols', ['name'])
    op.create_index('ix_symbols_source_file_id', 'symbols', ['source_file_id'])

    # ── code_chunks ─────────────────────────────────────────────────────
    # Embedding column: vector(1536) if pgvector active, else TEXT (JSON array)
    embedding_col = sa.Column('embedding', sa.Text(), nullable=True)

    op.create_table(
        'code_chunks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_file_id', sa.Uuid(), nullable=False),
        sa.Column('symbol_id', sa.Uuid(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        embedding_col,
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['source_file_id'], ['source_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_code_chunks_id', 'code_chunks', ['id'])
    op.create_index('ix_code_chunks_source_file_id', 'code_chunks', ['source_file_id'])
    op.create_index('ix_code_chunks_symbol_id', 'code_chunks', ['symbol_id'])

    # Alter embedding column to native vector type + create HNSW index
    if is_pg and pgvector_active:
        bind.execute(sa.text(
            "ALTER TABLE code_chunks ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector"
        ))
        bind.execute(sa.text(
            "CREATE INDEX idx_chunks_embedding "
            "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
        ))


def downgrade() -> None:
    op.drop_index('ix_code_chunks_symbol_id', table_name='code_chunks')
    op.drop_index('ix_code_chunks_source_file_id', table_name='code_chunks')
    op.drop_index('ix_code_chunks_id', table_name='code_chunks')
    op.drop_table('code_chunks')
    op.drop_index('ix_symbols_source_file_id', table_name='symbols')
    op.drop_index('ix_symbols_name', table_name='symbols')
    op.drop_index('ix_symbols_id', table_name='symbols')
    op.drop_table('symbols')
    op.drop_index('ix_source_files_repository_id', table_name='source_files')
    op.drop_index('ix_source_files_id', table_name='source_files')
    op.drop_table('source_files')
    op.drop_index('ix_repository_analyses_repository_id', table_name='repository_analyses')
    op.drop_index('ix_repository_analyses_id', table_name='repository_analyses')
    op.drop_table('repository_analyses')
