"""
Context retrieval service for CodeForge AI Agent (Step 7).
Retrieves repository architecture, frameworks, dependencies, symbols, and semantic code chunks
from Step 6 knowledge base to assemble a token-bounded context window for AI reasoning.
"""
import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.knowledge import RepositoryAnalysis, Symbol, SourceFile, CodeChunk
from app.services.chunker import estimate_tokens
from app.services.repository import get_safe_workspace_path, is_binary_file

logger = logging.getLogger("codeforge.agent.context")

MAX_CONTEXT_TOKENS = 12000
MAX_SOURCE_FILES = 8


@dataclass
class RetrievedContext:
    repository_id: str
    repository_name: str
    architecture_summary: str
    frameworks: List[str]
    entry_points: List[str]
    dependencies: Dict[str, str]
    relevant_symbols: List[Dict[str, Any]]
    relevant_chunks: List[Dict[str, Any]]
    files_analyzed: List[str]
    formatted_context: str
    token_count: int


def retrieve_task_context(
    db: Session,
    repository: Repository,
    task_description: str
) -> RetrievedContext:
    """
    Builds a bounded context window for a given agent task by leveraging
    Step 6 codebase analysis, AST symbols, and file tree.
    """
    repo_id = repository.id
    repo_name = repository.full_name or repository.name

    # 1. Fetch Repository Analysis metadata
    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.repository_id == repo_id
    ).first()

    arch_summary = analysis.architecture_summary if analysis and analysis.architecture_summary else "Standard codebase"
    frameworks = repository.frameworks or []
    entry_points = analysis.entry_points if analysis and analysis.entry_points else []
    deps = analysis.dependencies_parsed if analysis and analysis.dependencies_parsed else (repository.dependency_files or {})

    # 2. Extract symbols matching task description keywords
    cleaned_desc = task_description.replace(".py", " ").replace(".ts", " ").replace(".js", " ").replace(".go", " ")
    keywords = [w.lower().strip(".,;:?!()[]{}'\"") for w in cleaned_desc.split() if len(w.strip(".,;:?!()[]{}'\"")) >= 2]
    matching_symbols: List[Dict[str, Any]] = []
    
    if keywords:
        all_symbols = db.query(Symbol).join(SourceFile).filter(
            SourceFile.repository_id == repo_id
        ).all()
        for sym in all_symbols:
            name_lower = sym.name.lower()
            if any(kw in name_lower for kw in keywords):
                file_path = sym.source_file.path if sym.source_file else ""
                matching_symbols.append({
                    "name": sym.name,
                    "type": sym.type,
                    "file_path": file_path,
                    "line_number": sym.line_number
                })
                if len(matching_symbols) >= 15:
                    break

    # 3. Retrieve code chunks matching query keywords
    relevant_chunks: List[Dict[str, Any]] = []
    chunks_query = db.query(CodeChunk).join(SourceFile).filter(
        SourceFile.repository_id == repo_id
    )
    all_chunks = chunks_query.limit(100).all()
    for chunk in all_chunks:
        content_lower = chunk.content.lower()
        if any(kw in content_lower for kw in keywords):
            file_path = chunk.source_file.path if chunk.source_file else ""
            relevant_chunks.append({
                "file_path": file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "content": chunk.content,
                "symbol_name": getattr(chunk.symbol, "name", None) if chunk.symbol else None
            })
            if len(relevant_chunks) >= 10:
                break

    # 4. Identify key source files to include in context
    file_paths_to_read = set()
    # Always include entry points
    for ep in entry_points[:3]:
        file_paths_to_read.add(ep)
    # Include files from matching symbols and chunks
    for sym in matching_symbols:
        file_paths_to_read.add(sym["file_path"])
    for ch in relevant_chunks:
        file_paths_to_read.add(ch["file_path"])

    # If still few, fetch recent source files from DB
    if len(file_paths_to_read) < 3:
        source_files = db.query(SourceFile).filter(
            SourceFile.repository_id == repo_id
        ).limit(10).all()
        for sf in source_files:
            file_paths_to_read.add(sf.path)

    # 5. Read file contents safely up to token budget
    files_analyzed: List[str] = []
    file_contents_formatted: List[str] = []
    current_tokens = 0

    for rel_path in list(file_paths_to_read)[:MAX_SOURCE_FILES]:
        try:
            abs_path = get_safe_workspace_path(repository.local_path, rel_path)
            if not os.path.isfile(abs_path) or is_binary_file(abs_path):
                continue

            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(8000)  # Max ~8KB per file snippet

            file_tokens = estimate_tokens(content)
            if current_tokens + file_tokens > MAX_CONTEXT_TOKENS:
                break

            current_tokens += file_tokens
            files_analyzed.append(rel_path)
            file_contents_formatted.append(
                f"--- FILE: {rel_path} ---\n{content}"
            )
        except Exception as e:
            logger.warning(f"Could not read context file '{rel_path}': {str(e)}")

    # 6. Format final context window
    context_sections = [
        f"=== REPOSITORY OVERVIEW ===",
        f"Repository: {repo_name}",
        f"Architecture: {arch_summary}",
        f"Frameworks: {', '.join(frameworks) if frameworks else 'None'}",
        f"Entry Points: {', '.join(entry_points) if entry_points else 'None'}",
    ]

    if deps:
        dep_str = ", ".join([f"{k} ({v})" for k, v in list(deps.items())[:15]])
        context_sections.append(f"Dependencies: {dep_str}")

    if matching_symbols:
        sym_str = "\n".join([
            f"- {s['type']} {s['name']} at {s['file_path']}:{s['line_number']}"
            for s in matching_symbols[:10]
        ])
        context_sections.append(f"=== RELEVANT CODE SYMBOLS ===\n{sym_str}")

    if relevant_chunks:
        chunk_str = "\n---\n".join([
            f"File: {c['file_path']} (L{c['start_line']}-L{c['end_line']})\n{c['content']}"
            for c in relevant_chunks[:5]
        ])
        context_sections.append(f"=== RELEVANT CODE CHUNKS ===\n{chunk_str}")

    if file_contents_formatted:
        context_sections.append(f"=== SOURCE FILE CONTENTS ===\n" + "\n\n".join(file_contents_formatted))

    formatted_context = "\n\n".join(context_sections)
    total_tokens = estimate_tokens(formatted_context)

    return RetrievedContext(
        repository_id=str(repo_id),
        repository_name=repo_name,
        architecture_summary=arch_summary,
        frameworks=frameworks,
        entry_points=entry_points,
        dependencies=deps if isinstance(deps, dict) else {},
        relevant_symbols=matching_symbols,
        relevant_chunks=relevant_chunks,
        files_analyzed=files_analyzed,
        formatted_context=formatted_context,
        token_count=total_tokens
    )
