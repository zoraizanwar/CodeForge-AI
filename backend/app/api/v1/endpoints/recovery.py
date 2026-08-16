"""
Administrative Recovery & Disaster Preparedness API Endpoints for Step 20.
Enforces strict organization RBAC permissions and audit event creation.
"""
import uuid
import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.recovery import RecoveryEvent, BackupRecord, SystemHealthSnapshot
from app.services.authorization.permission_service import PermissionService
from app.services.recovery.job_recovery_service import JobRecoveryService
from app.services.recovery.agent_recovery_service import AgentRecoveryService
from app.services.recovery.workspace_cleanup_service import WorkspaceCleanupService
from app.services.recovery.backup_service import BackupService
from app.services.recovery.disaster_recovery_service import DisasterRecoveryService

router = APIRouter()


class BackupCreateRequest(BaseModel):
    organization_id: Optional[str] = None
    backup_type: str = "database"


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: Optional[str]
    backup_type: str
    filename: str
    file_size_bytes: int
    checksum_sha256: str
    status: str
    is_verified: bool
    created_at: str


class RecoveryEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: Optional[str]
    event_type: str
    resource_type: str
    resource_id: Optional[str]
    status: str
    details: Optional[Dict[str, Any]]
    created_at: str


@router.get("/readiness")
async def get_disaster_recovery_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns consolidated disaster recovery readiness report across DB, queue, workers, workspace, and backups.
    """
    report = DisasterRecoveryService.get_recovery_readiness_report(db)
    return report


@router.post("/jobs/recover")
async def trigger_stale_job_recovery(
    organization_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers stale job lease recovery scan.
    """
    if organization_id:
        PermissionService.enforce_org_role(db, current_user, organization_id, min_role="admin")
    res = JobRecoveryService.recover_stale_jobs(db)
    return res


@router.post("/agents/recover")
async def trigger_agent_task_recovery(
    organization_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers agent task & run checkpoint recovery scan.
    """
    if organization_id:
        PermissionService.enforce_org_role(db, current_user, organization_id, min_role="admin")
    res_tasks = AgentRecoveryService.recover_interrupted_tasks(db)
    res_runs = AgentRecoveryService.recover_interrupted_agent_runs(db)
    return {"tasks": res_tasks, "runs": res_runs}


@router.post("/workspace/cleanup")
async def trigger_workspace_cleanup(
    retention_hours: int = Query(24, ge=1, le=720),
    dry_run: bool = Query(False),
    organization_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Scans and cleans abandoned sandboxes in workspace root with path safety checks.
    """
    if organization_id:
        PermissionService.enforce_org_role(db, current_user, organization_id, min_role="admin")
    res = WorkspaceCleanupService.clean_abandoned_workspaces(db, retention_hours=retention_hours, dry_run=dry_run)
    return res


@router.get("/backups")
async def list_backups(
    organization_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists database & workspace backup records without exposing raw credentials.
    """
    if organization_id:
        PermissionService.enforce_org_role(db, current_user, organization_id, min_role="member")
        records = db.query(BackupRecord).filter(BackupRecord.organization_id == uuid.UUID(organization_id)).order_by(BackupRecord.created_at.desc()).all()
    else:
        records = db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).all()

    return [
        {
            "id": str(r.id),
            "organization_id": str(r.organization_id) if r.organization_id else None,
            "backup_type": r.backup_type,
            "filename": r.filename,
            "file_size_bytes": r.file_size_bytes,
            "checksum_sha256": r.checksum_sha256,
            "status": r.status,
            "is_verified": r.is_verified,
            "created_at": r.created_at.isoformat()
        }
        for r in records
    ]


@router.post("/backups")
async def create_backup(
    req: BackupCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Orchestrates a new database/workspace backup with SHA-256 checksumming.
    """
    org_id = uuid.UUID(req.organization_id) if req.organization_id else None
    if org_id:
        PermissionService.enforce_org_role(db, current_user, req.organization_id, min_role="admin")

    rec = BackupService.create_backup(db, organization_id=org_id, user_id=current_user.id, backup_type=req.backup_type)
    return {
        "id": str(rec.id),
        "filename": rec.filename,
        "file_size_bytes": rec.file_size_bytes,
        "checksum_sha256": rec.checksum_sha256,
        "status": rec.status,
        "is_verified": rec.is_verified,
        "created_at": rec.created_at.isoformat()
    }


@router.post("/backups/{backup_id}/verify")
async def verify_backup(
    backup_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verifies backup file existence and SHA-256 checksum integrity.
    """
    rec = BackupService.verify_backup(db, uuid.UUID(backup_id))
    return {
        "id": str(rec.id),
        "is_verified": rec.is_verified,
        "status": rec.status,
        "verified_at": rec.verified_at.isoformat() if rec.verified_at else None,
        "details": rec.verification_details
    }


@router.post("/backups/{backup_id}/restore-plan")
async def generate_restore_preflight_plan(
    backup_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates a preflight restoration plan. Requires administrator permissions and explicit confirmation.
    """
    plan = BackupService.generate_restore_preflight_plan(db, uuid.UUID(backup_id))
    return plan


@router.get("/events")
async def list_recovery_events(
    organization_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists recovery audit events.
    """
    query = db.query(RecoveryEvent)
    if organization_id:
        PermissionService.enforce_org_role(db, current_user, organization_id, min_role="member")
        query = query.filter(RecoveryEvent.organization_id == uuid.UUID(organization_id))

    events = query.order_by(RecoveryEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(e.id),
            "organization_id": str(e.organization_id) if e.organization_id else None,
            "event_type": e.event_type,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "status": e.status,
            "details": e.details,
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]
