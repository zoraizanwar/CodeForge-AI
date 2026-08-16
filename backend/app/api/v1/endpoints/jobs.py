"""
Job Management & Real-Time Monitoring API endpoints for CodeForge AI (Step 11).
"""
import uuid
import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.services.authorization.permission_service import PermissionService
from app.core.database import get_db, SessionLocal
from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.job import AgentJob
from app.schemas.job import (
    AgentJobResponseSchema,
    JobCancelResponseSchema
)
from app.services.jobs import JobManager, register_ws_listener, unregister_ws_listener

logger = logging.getLogger("codeforge.api.jobs")
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=List[AgentJobResponseSchema])
def list_jobs(
    repository_id: Optional[uuid.UUID] = Query(None),
    job_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists jobs for the authenticated user with optional filtering."""
    return JobManager.list_jobs(
        db,
        user_id=current_user.id,
        repository_id=repository_id,
        job_type=job_type,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/{job_id}", response_model=AgentJobResponseSchema)
def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves specific job details enforcing tenant isolation."""
    job = JobManager.get_job(db, job_id, current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or access denied."
        )
    return job


@router.post("/{job_id}/cancel", response_model=JobCancelResponseSchema)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cooperatively cancels a queued or running job."""
    try:
        job = await JobManager.cancel_job(db, job_id, current_user.id)
        return JobCancelResponseSchema(
            job_id=job.id,
            status=job.status,
            message="Job cancelled successfully."
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/{job_id}/retry", response_model=AgentJobResponseSchema)
async def retry_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually retries a failed or cancelled job."""
    try:
        return await JobManager.retry_job(db, job_id, current_user.id)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.websocket("/{job_id}/stream")
async def stream_job_updates(
    websocket: WebSocket,
    job_id: uuid.UUID,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Authenticated WebSocket endpoint streaming live job progress and stage updates.
    Sends final state immediately if job is already completed or failed.
    """
    await websocket.accept()

    # Authenticate token
    if not token:
        await websocket.send_json({"type": "error", "message": "Missing authentication token."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = None
    try:
        from app.services.auth import decode_access_token
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            user_id = uuid.UUID(payload["sub"])
            user = db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        logger.warning(f"WebSocket auth failed for job {job_id}: {e}")

    if not user:
        await websocket.send_json({"type": "error", "message": "Invalid or expired token."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify job ownership
    job = JobManager.get_job(db, job_id, user.id)
    if not job:
        await websocket.send_json({"type": "error", "message": "Job not found or access denied."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Immediately stream current state
    initial_dump = AgentJobResponseSchema.model_validate(job).model_dump(mode="json")
    await websocket.send_json({
        "type": "job_initial_state",
        "job": initial_dump,
        "message": f"Connected to job {job_id}. Current status: {job.status}"
    })

    # If job is already terminal, close stream gracefully
    if job.status in ["completed", "failed", "cancelled"]:
        await websocket.close()
        return

    register_ws_listener(job_id, websocket)

    # Keep connection alive with periodic heartbeats
    try:
        while True:
            await asyncio.sleep(settings.JOB_WS_HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "heartbeat", "timestamp": str(asyncio.get_event_loop().time())})
    except (WebSocketDisconnect, asyncio.CancelledError):
        logger.debug(f"WebSocket disconnected for job {job_id}")
    finally:
        unregister_ws_listener(job_id, websocket)
