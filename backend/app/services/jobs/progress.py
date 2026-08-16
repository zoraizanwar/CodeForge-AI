"""
Real-time progress tracker & event broadcaster for CodeForge AI jobs (Step 11).
Persists stage updates in PostgreSQL and streams updates to authenticated WebSocket listeners.
"""
import uuid
import datetime
import logging
import asyncio
from typing import Dict, Set, Any, Optional
from sqlalchemy.orm import Session
from app.models.job import AgentJob
from app.schemas.job import JobProgressUpdateSchema, AgentJobResponseSchema

logger = logging.getLogger("codeforge.jobs.progress")

# Active WebSocket connections grouped by job_id string
_WEBSOCKET_LISTENERS: Dict[str, Set[Any]] = {}


def register_ws_listener(job_id: uuid.UUID, websocket: Any) -> None:
    """Registers an active WebSocket connection for a given job_id."""
    str_id = str(job_id)
    if str_id not in _WEBSOCKET_LISTENERS:
        _WEBSOCKET_LISTENERS[str_id] = set()
    _WEBSOCKET_LISTENERS[str_id].add(websocket)


def unregister_ws_listener(job_id: uuid.UUID, websocket: Any) -> None:
    """Unregisters a WebSocket connection when client disconnects."""
    str_id = str(job_id)
    if str_id in _WEBSOCKET_LISTENERS:
        _WEBSOCKET_LISTENERS[str_id].discard(websocket)
        if not _WEBSOCKET_LISTENERS[str_id]:
            _WEBSOCKET_LISTENERS.pop(str_id, None)


async def broadcast_job_update(job_id: uuid.UUID, job_data: Dict[str, Any]) -> None:
    """Broadcasts a JSON update payload to all active WebSocket listeners for job_id."""
    str_id = str(job_id)
    listeners = list(_WEBSOCKET_LISTENERS.get(str_id, []))
    if not listeners:
        return

    dead_listeners = set()
    for ws in listeners:
        try:
            await ws.send_json(job_data)
        except Exception as e:
            logger.debug(f"Failed to send WS update to client for job {job_id}: {e}")
            dead_listeners.add(ws)

    for dead_ws in dead_listeners:
        unregister_ws_listener(job_id, dead_ws)


async def update_job_progress(
    db: Session,
    job_id: uuid.UUID,
    progress: int,
    stage: str,
    message: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    status: Optional[str] = None
) -> AgentJob:
    """
    Updates job progress and current stage in PostgreSQL DB and broadcasts real-time event.
    """
    job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found.")

    job.progress = max(0, min(100, progress))
    job.current_stage = stage
    job.updated_at = datetime.datetime.now(datetime.timezone.utc)

    if status:
        job.status = status
        if status == "running" and not job.started_at:
            job.started_at = datetime.datetime.now(datetime.timezone.utc)
        elif status in ["completed", "failed", "cancelled"]:
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)

    if result is not None:
        job.result = result

    if error_message is not None:
        job.error_message = error_message

    db.commit()
    db.refresh(job)

    # Convert to response dictionary for WebSocket streaming
    resp_schema = AgentJobResponseSchema.model_validate(job)
    event_payload = {
        "type": "job_update",
        "job": resp_schema.model_dump(mode="json"),
        "message": message or f"Stage: {stage} ({progress}%)"
    }

    # Broadcast update asynchronously
    asyncio.create_task(broadcast_job_update(job_id, event_payload))

    return job
