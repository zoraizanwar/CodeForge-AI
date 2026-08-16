"""
Centralized Context Builder for CodeForge AI Step 12 Multi-Agent Architecture.
Retrieves repository architecture, symbols, code chunks, dependencies, and previous step outputs.
Enforces token/size limits and strict secret isolation rules.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.agent import AgentTask
from app.models.multi_agent import AgentRun, AgentRunStep
from app.models.knowledge import RepositoryAnalysis, SourceFile, Symbol, CodeChunk
from app.services.agent.context_retriever import retrieve_task_context

logger = logging.getLogger("codeforge.agents.context")

# Sensitive keys and patterns that MUST NEVER enter prompt context
SECRET_KEY_SUBSTRINGS = [
    "api_key", "secret", "private_key", "password", "token", "jwt", "credential",
    "github_token", "installation_id", "access_key", "auth_header"
]


def _sanitize_dict(data: Any) -> Any:
    """Recursively removes sensitive keys, private _ keys, and non-serializable objects from context dicts."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).startswith("_"):
                continue
            if any(sub in str(k).lower() for sub in SECRET_KEY_SUBSTRINGS):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                try:
                    sanitized[k] = _sanitize_dict(v)
                except Exception:
                    continue
        return sanitized
    elif isinstance(data, list):
        res = []
        for item in data:
            try:
                res.append(_sanitize_dict(item))
            except Exception:
                pass
        return res
    elif isinstance(data, (str, int, float, bool, type(None))):
        if isinstance(data, str) and any(sub in data.lower() for sub in ["bearer ", "-----begin rsa private key-----", "-----begin private key-----"]):
            return "[REDACTED_SECRET_STRING]"
        return data
    return None


def build_agent_context(
    db: Session,
    run: AgentRun,
    agent_type: str,
    previous_steps: Optional[List[AgentRunStep]] = None
) -> Dict[str, Any]:
    """
    Builds customized, scoped context for a specialized agent step.
    Includes only necessary information, respecting token limits and secret sanitization.
    """
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    if not repo:
        raise ValueError(f"Repository {run.repository_id} not found.")

    task = db.query(AgentTask).filter(AgentTask.id == run.task_id).first() if run.task_id else None
    task_desc = task.task_description if task else "Architectural analysis & code generation"

    # Base task context from Step 7 retriever
    base_ctx = retrieve_task_context(db, repo, task_desc)

    context = {
        "run_id": str(run.id),
        "task_id": str(run.task_id) if run.task_id else None,
        "repository": {
            "id": str(repo.id),
            "name": repo.name,
            "full_name": repo.full_name,
            "default_branch": repo.default_branch,
            "local_path": repo.local_path,
        },
        "task_description": task_desc,
        "_retrieved_context": base_ctx,
        "repository_architecture": {
            "summary": base_ctx.architecture_summary,
            "frameworks": base_ctx.frameworks,
            "entry_points": base_ctx.entry_points,
        },
        "dependencies": base_ctx.dependencies,
        "symbols_count": len(base_ctx.relevant_symbols),
        "relevant_symbols": base_ctx.relevant_symbols[:15],
        "relevant_chunks": base_ctx.relevant_chunks[:15],  # Token limit
        "previous_outputs": {},
    }

    # Aggregate previous step outputs safely
    if previous_steps:
        for s in previous_steps:
            if s.output and s.status in ["passed", "completed", "review_needed"]:
                context["previous_outputs"][s.agent_type] = s.output

    return _sanitize_dict(context)
