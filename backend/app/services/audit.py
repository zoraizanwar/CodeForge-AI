"""
Centralized Audit Service for CodeForge AI Step 14 Production Observability & Audit Logging.
Provides safe, asynchronous-friendly recording of audit events with automatic secret redaction,
metadata size limits (10 KB max), and strict tenant boundaries.
"""
import json
import logging
import uuid
import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent
from app.core.logging import redact_secrets, request_id_ctx

logger = logging.getLogger("codeforge.audit")

MAX_METADATA_BYTES = 10 * 1024  # 10 KB size limit for metadata payload


def sanitize_audit_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Sanitizes audit metadata payload:
    1. Applies redact_secrets to mask sensitive tokens, keys, passwords.
    2. Enforces maximum 10 KB payload size limit.
    """
    if metadata is None:
        return None

    try:
        # Redact secrets recursively
        sanitized = redact_secrets(metadata)
        if not isinstance(sanitized, dict):
            sanitized = {"value": str(sanitized)}

        # Measure serialized JSON byte size
        encoded = json.dumps(sanitized, default=str)
        if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
            logger.warning("Audit metadata payload exceeded 10KB size limit. Truncating.")
            sanitized = {
                "summary": "Metadata payload truncated due to size limits (>10KB).",
                "_truncated": True,
                "preview": encoded[:1000]
            }
        return sanitized
    except Exception as exc:
        logger.error(f"Error sanitizing audit metadata: {exc}")
        return {"error": "Failed to sanitize metadata"}


def record_event(
    db: Session,
    event_type: str,
    severity: str = "info",
    user_id: Optional[uuid.UUID] = None,
    repository_id: Optional[uuid.UUID] = None,
    agent_task_id: Optional[uuid.UUID] = None,
    agent_run_id: Optional[uuid.UUID] = None,
    job_id: Optional[uuid.UUID] = None,
    request_id: Optional[str] = None,
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEvent]:
    """
    Records an immutable audit event record in the database.
    """
    try:
        req_id = request_id or request_id_ctx.get() or None
        safe_meta = sanitize_audit_metadata(metadata)

        event = AuditEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            repository_id=repository_id,
            agent_task_id=agent_task_id,
            agent_run_id=agent_run_id,
            job_id=job_id,
            event_type=event_type,
            severity=severity,
            request_id=req_id,
            success=success,
            meta=safe_meta,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as exc:
        logger.error(f"Failed to record audit event '{event_type}': {exc}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def record_security_event(
    db: Session,
    event_type: str,
    severity: str = "warning",
    user_id: Optional[uuid.UUID] = None,
    repository_id: Optional[uuid.UUID] = None,
    request_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEvent]:
    """Helper for security-related audit events (path traversal, auth failures, forbidden operations)."""
    return record_event(
        db=db,
        event_type=f"security.{event_type}",
        severity=severity,
        user_id=user_id,
        repository_id=repository_id,
        request_id=request_id,
        success=False,
        metadata=metadata
    )


def record_agent_event(
    db: Session,
    event_type: str,
    user_id: Optional[uuid.UUID] = None,
    repository_id: Optional[uuid.UUID] = None,
    agent_task_id: Optional[uuid.UUID] = None,
    agent_run_id: Optional[uuid.UUID] = None,
    severity: str = "info",
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEvent]:
    """Helper for single/multi-agent workflow events (planner, engineer, reviewer, tester, repair)."""
    return record_event(
        db=db,
        event_type=f"agent.{event_type}",
        severity=severity,
        user_id=user_id,
        repository_id=repository_id,
        agent_task_id=agent_task_id,
        agent_run_id=agent_run_id,
        success=success,
        metadata=metadata
    )


def record_job_event(
    db: Session,
    event_type: str,
    job_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    repository_id: Optional[uuid.UUID] = None,
    severity: str = "info",
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEvent]:
    """Helper for background job lifecycle events (queued, started, completed, retried, failed, cancelled)."""
    return record_event(
        db=db,
        event_type=f"job.{event_type}",
        severity=severity,
        user_id=user_id,
        repository_id=repository_id,
        job_id=job_id,
        success=success,
        metadata=metadata
    )


def record_repository_event(
    db: Session,
    event_type: str,
    repository_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    severity: str = "info",
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEvent]:
    """Helper for repository import, indexing, and deletion events."""
    return record_event(
        db=db,
        event_type=f"repository.{event_type}",
        severity=severity,
        user_id=user_id,
        repository_id=repository_id,
        success=success,
        metadata=metadata
    )


def record_git_event(
    db: Session,
    event_type: str,
    user_id: Optional[uuid.UUID] = None,
    repository_id: Optional[uuid.UUID] = None,
    agent_task_id: Optional[uuid.UUID] = None,
    severity: str = "info",
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEvent]:
    """Helper for Git operations and Pull Request creation events."""
    return record_event(
        db=db,
        event_type=f"git.{event_type}",
        severity=severity,
        user_id=user_id,
        repository_id=repository_id,
        agent_task_id=agent_task_id,
        success=success,
        metadata=metadata
    )
