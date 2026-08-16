"""
Repository analysis pipeline for CodeForge AI (Step 6).

Orchestrates:
  1. File scanning with hash-based incremental detection
  2. Language classification
  3. AST parsing / symbol extraction
  4. Semantic chunking
  5. Embedding generation
  6. Database persistence
  7. Dependency analysis
  8. Architecture detection
  9. RepositoryAnalysis metadata update

All filesystem access respects Step 5 workspace isolation and exclusion rules.
Never processes .env, .pem, private keys, credentials, or binaries.
"""
import datetime
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import (
    CodeChunk,
    RepositoryAnalysis,
    SourceFile,
    Symbol,
)
from app.models.repository import Repository
from app.services.code_parser import (
    EXCLUDED_DIRS,
    EXCLUDED_EXTENSIONS,
    EXCLUDED_FILENAMES,
    detect_language,
    parse_file,
)
from app.services.dependency_parser import (
    DEPENDENCY_FILENAMES,
    detect_frameworks,
    parse_dependency_file,
)
from app.services.embeddings import get_embedding_provider

logger = logging.getLogger("codeforge.analysis")

MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB — same as Step 5 file reader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


def _iter_workspace_files(workspace_path: Path):
    """
    Walk the repository workspace, yielding (relative_path, absolute_path)
    tuples for every non-excluded, non-sensitive file.
    """
    for root, dirs, files in os.walk(workspace_path):
        # Prune excluded directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS and not d.startswith(".")
        ]
        for filename in files:
            abs_path = Path(root) / filename
            relative = abs_path.relative_to(workspace_path)
            relative_str = str(relative).replace("\\", "/")

            # Check filename exclusions
            if filename.lower() in EXCLUDED_FILENAMES:
                continue
            # Check extension exclusions
            if abs_path.suffix.lower() in EXCLUDED_EXTENSIONS:
                continue
            # Size guard
            try:
                if abs_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    logger.debug("Skipping oversized file: %s", relative_str)
                    continue
            except OSError:
                continue

            yield relative_str, abs_path


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

async def run_analysis_pipeline(
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
) -> None:
    """
    Full analysis pipeline for a repository.
    Runs as a FastAPI BackgroundTask.
    Sets RepositoryAnalysis.status to processing → completed/failed.

    NOTE: db is injected from the endpoint — Starlette runs background tasks
    synchronously before response delivery in TestClient, so the session
    remains valid within the request lifecycle.
    """
    # ── Fetch / create RepositoryAnalysis record ─────────────────────────
    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.repository_id == repository_id
    ).first()
    if not analysis:
        analysis = RepositoryAnalysis(
            repository_id=repository_id,
            status="processing",
        )
        db.add(analysis)
    else:
        analysis.status = "processing"
        analysis.error_message = None
    db.commit()

    # ── Fetch repository, verify ownership ───────────────────────────────
    repo: Optional[Repository] = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.user_id == user_id,
    ).first()

    if not repo:
        analysis.status = "failed"
        analysis.error_message = "Repository not found or access denied"
        db.commit()
        return

    workspace_root = Path(settings.WORKSPACE_ROOT)
    repo_workspace: Optional[Path] = None
    if repo.local_path and Path(repo.local_path).exists():
        repo_workspace = Path(repo.local_path)
    else:
        candidate_gh = workspace_root / f"user_{user_id}" / f"repo_{repo.github_repo_id}"
        candidate_db = workspace_root / f"user_{user_id}" / f"repo_{repo.id}"
        if candidate_gh.exists():
            repo_workspace = candidate_gh
        elif candidate_db.exists():
            repo_workspace = candidate_db

    if not repo_workspace or not repo_workspace.exists():
        analysis.status = "failed"
        analysis.error_message = "Repository workspace not found. Please re-import."
        db.commit()
        return


    embedding_provider = get_embedding_provider()

    try:
        all_dependencies: dict = {}
        go_mod_content: str = ""
        file_count = 0
        error_count = 0
        entry_points: list[str] = []

        ENTRY_POINT_NAMES = {
            "main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
            "manage.py", "index.js", "index.ts", "main.ts", "main.go",
            "main.rs", "App.tsx", "App.jsx",
        }

        # ── Scan workspace files ──────────────────────────────────────────
        for relative_path, abs_path in _iter_workspace_files(repo_workspace):
            file_count += 1
            filename = Path(relative_path).name
            language = detect_language(relative_path)
            if language is None:
                continue

            try:
                raw_bytes = abs_path.read_bytes()
                file_hash = _sha256(raw_bytes)
                file_size = len(raw_bytes)

                # Detect entry points
                if filename in ENTRY_POINT_NAMES:
                    entry_points.append(relative_path)

                # Parse dependency files
                if filename in DEPENDENCY_FILENAMES:
                    try:
                        source_text = raw_bytes.decode("utf-8", errors="replace")
                        deps = parse_dependency_file(filename, source_text)
                        all_dependencies.update(deps)
                        if filename == "go.mod":
                            go_mod_content = source_text
                    except Exception as dep_err:
                        logger.warning("Dep parse error %s: %s", relative_path, dep_err)

                # ── Incremental: skip unchanged files ─────────────────────
                existing_file: Optional[SourceFile] = db.query(SourceFile).filter(
                    SourceFile.repository_id == repository_id,
                    SourceFile.path == relative_path,
                ).first()

                if existing_file and existing_file.hash == file_hash:
                    logger.debug("Skipping unchanged file: %s", relative_path)
                    continue

                # ── Decode text ───────────────────────────────────────────
                try:
                    source_text = raw_bytes.decode("utf-8", errors="replace")
                except Exception:
                    continue

                # ── Persist or update SourceFile ──────────────────────────
                if existing_file:
                    # File changed: delete old symbols/chunks via cascade
                    db.delete(existing_file)
                    db.flush()

                source_file = SourceFile(
                    repository_id=repository_id,
                    path=relative_path,
                    language=language,
                    size_bytes=file_size,
                    hash=file_hash,
                )
                db.add(source_file)
                db.flush()  # get source_file.id

                # ── AST parse ────────────────────────────────────────────
                parse_result = parse_file(relative_path, source_text, language)
                if parse_result.error:
                    logger.warning(
                        "Parse error in %s: %s", relative_path, parse_result.error
                    )

                # ── Persist symbols ───────────────────────────────────────
                symbol_db_map: dict[tuple, Symbol] = {}
                for sym in parse_result.symbols:
                    if sym.type == "import":
                        continue  # don't persist imports as symbols
                    symbol_record = Symbol(
                        source_file_id=source_file.id,
                        name=sym.name,
                        type=sym.type,
                        line_number=sym.line_number,
                        end_line_number=sym.end_line_number,
                        metadata_json=sym.metadata or {},
                    )
                    db.add(symbol_record)
                    db.flush()
                    symbol_db_map[(sym.name, sym.line_number)] = symbol_record

                # ── Semantic chunking ─────────────────────────────────────
                from app.services.chunker import chunk_file  # lazy import
                chunks = chunk_file(relative_path, source_text, language, parse_result)

                for chunk in chunks:
                    # Find matching symbol for this chunk
                    sym_record: Optional[Symbol] = None
                    if chunk.symbol_name:
                        for (name, _), sym in symbol_db_map.items():
                            if name == chunk.symbol_name:
                                sym_record = sym
                                break

                    # Generate embedding
                    try:
                        embedding_vector = await embedding_provider.get_embedding(chunk.content)
                    except Exception as emb_err:
                        logger.warning("Embedding error: %s", emb_err)
                        embedding_vector = None

                    chunk_record = CodeChunk(
                        source_file_id=source_file.id,
                        symbol_id=sym_record.id if sym_record else None,
                        content=chunk.content,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        embedding=embedding_vector,
                        token_count=chunk.token_count,
                    )
                    db.add(chunk_record)

                db.commit()

            except Exception as file_err:
                error_count += 1
                logger.error("Error processing file %s: %s", relative_path, file_err)
                db.rollback()
                # Continue processing other files

        # ── Detect frameworks ─────────────────────────────────────────────
        frameworks = detect_frameworks(all_dependencies)

        # ── Architecture summary ──────────────────────────────────────────
        architecture_summary = _build_architecture_summary(
            repo, frameworks, all_dependencies, entry_points, file_count, error_count
        )

        # ── Update RepositoryAnalysis ─────────────────────────────────────
        analysis.status = "completed"
        analysis.entry_points = entry_points
        analysis.dependencies_parsed = all_dependencies
        analysis.architecture_summary = architecture_summary
        analysis.last_analyzed_at = datetime.datetime.now(datetime.timezone.utc)
        analysis.error_message = (
            f"Completed with {error_count} file error(s)." if error_count else None
        )
        db.commit()

        logger.info(
            "Analysis complete for repo %s: %d files, %d errors, frameworks=%s",
            repo.full_name, file_count, error_count, frameworks,
        )

    except Exception as exc:
        logger.exception("Analysis pipeline failed for repo %s", repository_id)
        try:
            db.rollback()
            analysis = db.query(RepositoryAnalysis).filter(
                RepositoryAnalysis.repository_id == repository_id
            ).first()
            if analysis:
                analysis.status = "failed"
                analysis.error_message = f"Analysis pipeline failed: {type(exc).__name__}"
                db.commit()
        except Exception as inner:
            logger.error("Failed to update analysis status: %s", inner)


def _build_architecture_summary(
    repo,
    frameworks: list[str],
    dependencies: dict,
    entry_points: list[str],
    file_count: int,
    error_count: int,
) -> str:
    parts = [f"Repository: {repo.full_name}"]
    if frameworks:
        parts.append(f"Detected frameworks: {', '.join(frameworks)}")
    if entry_points:
        parts.append(f"Entry points: {', '.join(entry_points[:5])}")
    if dependencies:
        parts.append(f"Dependencies: {len(dependencies)} packages")
    parts.append(f"Indexed {file_count} files with {error_count} errors.")
    return " | ".join(parts)
