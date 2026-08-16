"""
API endpoints for CodeForge AI Step 12 Multi-Agent Software Engineering Workflows.
Provides endpoints for triggering, querying, cancelling, retrying, and WebSocket streaming multi-agent runs.
"""
import uuid
import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.services.authorization.permission_service import PermissionService
from app.core.database import get_db, SessionLocal
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import AgentTask
from app.models.multi_agent import AgentRun, AgentRunStep
from app.schemas.agent_runs import AgentRunResponseSchema, AgentRunStepResponseSchema, AgentRunCreateSchema
from app.services.jobs import JobManager, register_ws_listener, unregister_ws_listener

logger = logging.getLogger("codeforge.api.agent_runs")
router = APIRouter()


def _get_user_repository(repo_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> Repository:
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == user_id
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found or access denied."
        )
    return repo


@router.post(
    "/repositories/{repo_id}/agent/runs",
    response_model=AgentRunResponseSchema,
    status_code=status.HTTP_202_ACCEPTED
)
async def start_multi_agent_run(
    repo_id: uuid.UUID,
    payload: AgentRunCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers a new Multi-Agent Software Engineering workflow run.
    Enqueues a durable Step 11 multi_agent_run job.
    """
    repo = _get_user_repository(repo_id, current_user.id, db)

    task_id = payload.task_id
    if not task_id:
        # Create an underlying task if not supplied
        task = AgentTask(
            id=uuid.uuid4(),
            user_id=current_user.id,
            repository_id=repo.id,
            task_description=payload.task_description,
            status="pending"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=current_user.id,
        repository_id=repo.id,
        task_id=task_id,
        status="pending",
        current_agent="planner",
        workflow_stage="queued",
        overall_progress=0
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Enqueue durable job
    job = JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=repo.id,
        job_type="multi_agent_run",
        task_id=task_id,
        payload={"run_id": str(run.id)}
    )

    run.parent_job_id = job.id
    db.commit()
    db.refresh(run)

    return run


@router.get(
    "/repositories/{repo_id}/agent/runs",
    response_model=List[AgentRunResponseSchema]
)
async def list_agent_runs(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all multi-agent runs for a repository."""
    repo = _get_user_repository(repo_id, current_user.id, db)
    return db.query(AgentRun).filter(
        AgentRun.repository_id == repo.id,
        AgentRun.user_id == current_user.id
    ).order_by(AgentRun.created_at.desc()).all()


@router.get(
    "/repositories/{repo_id}/agent/runs/{run_id}",
    response_model=AgentRunResponseSchema
)
async def get_agent_run_detail(
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves full details for a specific multi-agent run."""
    repo = _get_user_repository(repo_id, current_user.id, db)
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.repository_id == repo.id,
        AgentRun.user_id == current_user.id
    ).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found or access denied."
        )
    return run


@router.get(
    "/repositories/{repo_id}/agent/runs/{run_id}/steps",
    response_model=List[AgentRunStepResponseSchema]
)
async def list_agent_run_steps(
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists individual agent steps executed in a workflow run."""
    repo = _get_user_repository(repo_id, current_user.id, db)
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.repository_id == repo.id,
        AgentRun.user_id == current_user.id
    ).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found or access denied."
        )
    return run.steps


@router.post(
    "/repositories/{repo_id}/agent/runs/{run_id}/cancel",
    response_model=AgentRunResponseSchema
)
async def cancel_agent_run(
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancels a running multi-agent workflow."""
    repo = _get_user_repository(repo_id, current_user.id, db)
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.repository_id == repo.id,
        AgentRun.user_id == current_user.id
    ).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found or access denied."
        )

    run.status = "cancelled"
    run.completed_at = datetime.datetime.now(datetime.timezone.utc)
    run.error_message = "Cancelled by user action."

    if run.parent_job_id:
        await JobManager.cancel_job(db, run.parent_job_id, current_user.id)

    db.commit()
    db.refresh(run)
    return run


@router.post(
    "/repositories/{repo_id}/agent/runs/{run_id}/retry",
    response_model=AgentRunResponseSchema,
    status_code=status.HTTP_202_ACCEPTED
)
async def retry_agent_run(
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retries a failed or cancelled multi-agent run."""
    repo = _get_user_repository(repo_id, current_user.id, db)
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.repository_id == repo.id,
        AgentRun.user_id == current_user.id
    ).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found or access denied."
        )

    run.status = "pending"
    run.error_message = None
    db.commit()

    if run.parent_job_id:
        await JobManager.retry_job(db, run.parent_job_id, current_user.id)

    db.refresh(run)
    return run


@router.websocket("/repositories/{repo_id}/agent/runs/{run_id}/stream")
async def stream_agent_run_updates(
    websocket: WebSocket,
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Authenticated WebSocket endpoint streaming live progress and step events for a multi-agent run.
    """
    await websocket.accept()

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
        logger.warning(f"WebSocket auth failed for agent run {run_id}: {e}")

    if not user:
        await websocket.send_json({"type": "error", "message": "Invalid or expired token."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.repository_id == repo_id,
        AgentRun.user_id == user.id
    ).first()

    if not run:
        await websocket.send_json({"type": "error", "message": "Agent run not found or access denied."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Stream initial dump
    dump = AgentRunResponseSchema.model_validate(run).model_dump(mode="json")
    await websocket.send_json({
        "type": "run_initial_state",
        "run": dump,
        "message": f"Connected to run {run_id}. Current status: {run.status}"
    })

    if run.parent_job_id:
        register_ws_listener(run.parent_job_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if run.parent_job_id:
            unregister_ws_listener(run.parent_job_id, websocket)
