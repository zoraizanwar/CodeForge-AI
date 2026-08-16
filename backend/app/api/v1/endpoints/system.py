"""
System Monitoring & Operational Statistics API for CodeForge AI Step 14.
Provides user-scoped operational stats and audit log retention cleanup controls.
"""
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.metrics import metrics_collector
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import AgentTask, AgentExecution
from app.models.job import AgentJob
from app.models.multi_agent import AgentRun
from app.models.audit import AuditEvent
from app.services.audit_cleanup import cleanup_expired_audit_events

router = APIRouter()


@router.get("/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns operational statistics scoped to the authenticated user's permitted resources.
    Combines aggregated system metrics with user resource counts.
    """
    # User-scoped counts
    repo_count = db.query(Repository).filter(Repository.user_id == current_user.id).count()
    task_count = db.query(AgentTask).filter(AgentTask.user_id == current_user.id).count()
    job_count = db.query(AgentJob).filter(AgentJob.user_id == current_user.id).count()
    run_count = db.query(AgentRun).filter(AgentRun.user_id == current_user.id).count()

    # Success rate counts for user's executions
    user_execs = db.query(AgentExecution).join(AgentTask).filter(AgentTask.user_id == current_user.id).all()
    total_execs = len(user_execs)
    passed_execs = len([e for e in user_execs if e.status == "passed"])
    exec_success_rate = round((passed_execs / total_execs * 100.0), 1) if total_execs > 0 else 100.0

    # User recent security events
    recent_security_events = db.query(AuditEvent).filter(
        AuditEvent.user_id == current_user.id,
        AuditEvent.event_type.startswith("security.")
    ).order_by(AuditEvent.created_at.desc()).limit(10).all()

    formatted_security = [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "severity": e.severity,
            "request_id": e.request_id,
            "created_at": e.created_at.isoformat(),
            "metadata": e.meta,
        }
        for e in recent_security_events
    ]

    metrics_snapshot = metrics_collector.get_metrics_snapshot()

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metrics": metrics_snapshot,
        "user_stats": {
            "repositories": repo_count,
            "tasks": task_count,
            "jobs": job_count,
            "multi_agent_runs": run_count,
            "execution_success_rate": exec_success_rate,
            "security_events": formatted_security,
        }
    }


@router.post("/audit/cleanup")
async def trigger_audit_cleanup(
    retention_days: Optional[int] = Query(None, ge=1, le=365, description="Days to retain audit logs"),
    dry_run: bool = Query(False, description="Perform dry-run check without deleting records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers audit retention cleanup for expired records.
    """
    res = cleanup_expired_audit_events(db, retention_days=retention_days, dry_run=dry_run)
    return res
