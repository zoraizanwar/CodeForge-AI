"""
FastAPI endpoints for repository intelligence (Step 6).

All endpoints require JWT authentication and enforce repository ownership.

Routes:
  GET  /api/v1/repositories/{repo_id}/analysis
  GET  /api/v1/repositories/{repo_id}/symbols
  GET  /api/v1/repositories/{repo_id}/dependencies
  POST /api/v1/repositories/{repo_id}/analyze
  POST /api/v1/repositories/{repo_id}/search
"""
import json
import logging
import math
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.knowledge import CodeChunk, RepositoryAnalysis, SourceFile, Symbol
from app.models.repository import Repository
from app.models.user import User
from app.schemas.analysis import (
    AnalysisStatusResponse,
    DependenciesResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SymbolResponse,
)
from app.services.analysis import run_analysis_pipeline
from app.services.dependency_parser import detect_frameworks
from app.services.embeddings import get_embedding_provider
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger("codeforge.api.analysis")
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_repo_owned(
    repo_id: uuid.UUID,
    current_user: User,
    db: Session,
) -> Repository:
    """Return repo if owned by current_user, else raise 404."""
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id,
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )
    return repo


def _cosine_similarity_python(a: list, b: list) -> float:
    """Pure-Python cosine similarity for SQLite fallback."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# GET /analysis
# ---------------------------------------------------------------------------

@router.get("/{repo_id}/analysis", response_model=AnalysisStatusResponse)
async def get_analysis(
    repo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the latest analysis metadata for a repository."""
    repo = _get_repo_owned(repo_id, current_user, db)

    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.repository_id == repo.id
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository has not been analyzed yet. POST /analyze to trigger.",
        )

    # Compute frameworks from persisted dependencies
    frameworks: List[str] = []
    if analysis.dependencies_parsed:
        frameworks = detect_frameworks(analysis.dependencies_parsed)

    return AnalysisStatusResponse(
        id=analysis.id,
        repository_id=analysis.repository_id,
        status=analysis.status,
        architecture_summary=analysis.architecture_summary,
        entry_points=analysis.entry_points,
        dependencies_parsed=analysis.dependencies_parsed,
        frameworks=frameworks,
        last_analyzed_at=analysis.last_analyzed_at,
        error_message=analysis.error_message,
    )


# ---------------------------------------------------------------------------
# GET /symbols
# ---------------------------------------------------------------------------

@router.get("/{repo_id}/symbols", response_model=List[SymbolResponse])
async def get_symbols(
    repo_id: uuid.UUID,
    symbol_type: Optional[str] = Query(default=None, description="Filter by type: class, function, method, route"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return AST-extracted symbols for a repository."""
    repo = _get_repo_owned(repo_id, current_user, db)

    query = (
        db.query(Symbol, SourceFile.path)
        .join(SourceFile, Symbol.source_file_id == SourceFile.id)
        .filter(SourceFile.repository_id == repo.id)
    )
    if symbol_type:
        query = query.filter(Symbol.type == symbol_type)

    rows = query.offset(offset).limit(limit).all()

    return [
        SymbolResponse(
            id=sym.id,
            name=sym.name,
            type=sym.type,
            file_path=path,
            line_number=sym.line_number,
            end_line_number=sym.end_line_number,
            metadata=sym.metadata_json,
        )
        for sym, path in rows
    ]


# ---------------------------------------------------------------------------
# GET /dependencies
# ---------------------------------------------------------------------------

@router.get("/{repo_id}/dependencies", response_model=DependenciesResponse)
async def get_dependencies(
    repo_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return parsed dependency list and detected frameworks."""
    repo = _get_repo_owned(repo_id, current_user, db)

    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.repository_id == repo.id
    ).first()

    deps: dict = {}
    frameworks: List[str] = []
    if analysis and analysis.dependencies_parsed:
        deps = analysis.dependencies_parsed
        frameworks = detect_frameworks(deps)

    return DependenciesResponse(
        repository_id=repo.id,
        dependencies=deps,
        frameworks=frameworks,
    )


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

@router.post("/{repo_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    repo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a full background analysis pipeline for the repository."""
    repo = _get_repo_owned(repo_id, current_user, db)

    if repo.status not in ("indexed", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository is in status '{repo.status}'. Wait for import to complete.",
        )

    # Ensure analysis record exists and set status to pending
    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.repository_id == repo.id
    ).first()
    if analysis:
        analysis.status = "pending"
        analysis.error_message = None
    else:
        analysis = RepositoryAnalysis(
            repository_id=repo.id,
            status="pending"
        )
        db.add(analysis)
    db.commit()

    from app.services.jobs import JobManager
    JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=repo.id,
        job_type="analysis"
    )

    return {
        "message": "Analysis queued",
        "repository_id": str(repo.id),
        "status": "queued",
    }


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

@router.post("/{repo_id}/search", response_model=SearchResponse)
async def search_repository(
    repo_id: uuid.UUID,
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic code search over repository chunks.
    Uses pgvector cosine similarity on PostgreSQL.
    Falls back to pure-Python cosine similarity on SQLite.
    Only returns chunks owned by the authenticated user.
    """
    repo = _get_repo_owned(repo_id, current_user, db)

    # Generate query embedding
    embedding_provider = get_embedding_provider()
    try:
        query_vector = await embedding_provider.get_embedding(request.query)
    except Exception as exc:
        logger.error("Failed to generate query embedding: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service temporarily unavailable",
        )

    dialect_name = "sqlite"
    try:
        bind = db.get_bind()
        if bind is not None:
            dialect_name = bind.dialect.name
    except Exception:
        pass


    results: List[SearchResultItem] = []

    if dialect_name == "postgresql":
        # ── pgvector path ───────────────────────────────────────────────
        try:
            from pgvector.sqlalchemy import Vector
            # Build a parameterized cosine distance query
            # Only includes chunks belonging to this user's repository
            rows = (
                db.query(
                    CodeChunk,
                    SourceFile.path,
                    SourceFile.language,
                    Symbol.name.label("symbol_name"),
                )
                .join(SourceFile, CodeChunk.source_file_id == SourceFile.id)
                .outerjoin(Symbol, CodeChunk.symbol_id == Symbol.id)
                .filter(SourceFile.repository_id == repo.id)
                .filter(CodeChunk.embedding.isnot(None))
                .order_by(CodeChunk.embedding.cosine_distance(query_vector))
                .limit(request.top_k)
                .all()
            )
            for chunk, path, language, symbol_name in rows:
                results.append(SearchResultItem(
                    chunk_id=chunk.id,
                    file_path=path,
                    language=language,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    symbol_name=symbol_name,
                    score=None,  # distance not easily extracted here
                ))
        except Exception as pg_err:
            logger.warning("pgvector search failed, falling back to Python: %s", pg_err)
            dialect_name = "sqlite"  # trigger fallback

    if dialect_name != "postgresql":
        # ── Python cosine fallback (SQLite / pgvector unavailable) ────────
        rows = (
            db.query(
                CodeChunk,
                SourceFile.path,
                SourceFile.language,
                Symbol.name.label("symbol_name"),
            )
            .join(SourceFile, CodeChunk.source_file_id == SourceFile.id)
            .outerjoin(Symbol, CodeChunk.symbol_id == Symbol.id)
            .filter(SourceFile.repository_id == repo.id)
            .filter(CodeChunk.embedding.isnot(None))
            .all()
        )

        scored = []
        for chunk, path, language, symbol_name in rows:
            emb = chunk.embedding
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    continue
            if not emb:
                continue
            sim = _cosine_similarity_python(query_vector, emb)
            scored.append((sim, chunk, path, language, symbol_name))

        # Sort by descending similarity, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        for sim, chunk, path, language, symbol_name in scored[: request.top_k]:
            results.append(SearchResultItem(
                chunk_id=chunk.id,
                file_path=path,
                language=language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                symbol_name=symbol_name,
                score=round(sim, 4),
            ))

    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
    )
