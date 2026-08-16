"""
Authenticated Audit REST API endpoints for CodeForge AI Step 14 Observability.
Provides tenant-isolated audit event querying, filtering, and detail inspection.
"""
import uuid
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventResponseSchema, AuditEventListResponseSchema

router = APIRouter()


@router.get("", response_model=AuditEventListResponseSchema)
async def list_audit_events(
    event_type: Optional[str] = Query(None, description="Filter by event type prefix or exact name"),
    severity: Optional[str] = Query(None, description="Filter by severity level (info, warning, error, critical)"),
    success: Optional[bool] = Query(None, description="Filter by success flag"),
    repository_id: Optional[uuid.UUID] = Query(None, description="Filter by repository ID"),
    agent_task_id: Optional[uuid.UUID] = Query(None, description="Filter by agent task ID"),
    request_id: Optional[str] = Query(None, description="Filter by correlation request ID"),
    start_date: Optional[datetime.datetime] = Query(None, description="Filter events on or after timestamp"),
    end_date: Optional[datetime.datetime] = Query(None, description="Filter events on or before timestamp"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves filtered audit event records scoped exclusively to the authenticated user.
    Enforces strict tenant isolation.
    """
    query = db.query(AuditEvent).filter(AuditEvent.user_id == current_user.id)

    if event_type:
        if "*" in event_type or "%" in event_type:
            clean_type = event_type.replace("*", "%")
            query = query.filter(AuditEvent.event_type.like(clean_type))
        else:
            query = query.filter(AuditEvent.event_type.startswith(event_type))

    if severity:
        query = query.filter(AuditEvent.severity == severity.lower())

    if success is not None:
        query = query.filter(AuditEvent.success == success)

    if repository_id:
        query = query.filter(AuditEvent.repository_id == repository_id)

    if agent_task_id:
        query = query.filter(AuditEvent.agent_task_id == agent_task_id)

    if request_id:
        query = query.filter(AuditEvent.request_id == request_id)

    if start_date:
        query = query.filter(AuditEvent.created_at >= start_date)

    if end_date:
        query = query.filter(AuditEvent.created_at <= end_date)

    total = query.count()
    events = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()

    # Map meta to metadata for schema response
    formatted_items = []
    for item in events:
        resp = AuditEventResponseSchema(
            id=item.id,
            user_id=item.user_id,
            repository_id=item.repository_id,
            agent_task_id=item.agent_task_id,
            agent_run_id=item.agent_run_id,
            job_id=item.job_id,
            event_type=item.event_type,
            severity=item.severity,
            request_id=item.request_id,
            success=item.success,
            metadata=item.meta,
            created_at=item.created_at
        )
        formatted_items.append(resp)

    return AuditEventListResponseSchema(
        total=total,
        items=formatted_items,
        limit=limit,
        offset=offset
    )


@router.get("/{event_id}", response_model=AuditEventResponseSchema)
async def get_audit_event_detail(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves detail view for a specific audit event record.
    Enforces tenant isolation ownership check.
    """
    event = db.query(AuditEvent).filter(
        AuditEvent.id == event_id,
        AuditEvent.user_id == current_user.id
    ).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit event not found or access denied."
        )

    return AuditEventResponseSchema(
        id=event.id,
        user_id=event.user_id,
        repository_id=event.repository_id,
        agent_task_id=event.agent_task_id,
        agent_run_id=event.agent_run_id,
        job_id=event.job_id,
        event_type=event.event_type,
        severity=event.severity,
        request_id=event.request_id,
        success=event.success,
        metadata=event.meta,
        created_at=event.created_at
    )
