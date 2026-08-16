"""
FastAPI endpoints for AI Software Engineer Agent API, Execution, GitHub PR Automation, & Feedback Loop Repair (Step 7, 8, 9, & 10).

All endpoints require JWT authentication and enforce strict repository & task ownership.

Routes:
  POST /api/v1/repositories/{repo_id}/agent/tasks
  GET  /api/v1/repositories/{repo_id}/agent/tasks
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/plan
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/changes
  POST /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/execute
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/executions
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/executions/{execution_id}
  POST /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/approve
  POST /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/pull-request
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/git-operations
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/pull-request
  POST /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/repair
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/iterations
  GET  /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/iterations/{iteration_id}
  POST /api/v1/repositories/{repo_id}/agent/tasks/{task_id}/iterations/{iteration_id}/retry
"""
import os
import uuid
import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.services.authorization.permission_service import PermissionService
from app.core.database import get_db
from app.models.repository import Repository
from app.models.agent import AgentTask, AgentExecution, GitOperation, AgentIteration
from app.models.user import User
from app.schemas.agent import (
    TaskCreateRequest,
    AgentTaskResponse,
    AgentTaskChangesResponse,
    ImplementationPlanSchema,
    FileChangeSchema,
    AgentExecutionResponse,
    GitOperationResponse,
    AgentIterationResponse
)
from app.services.agent.orchestrator import run_agent_task_pipeline
from app.services.execution.manager import execute_agent_task_execution_pipeline
from app.services.git.patch_fingerprint import compute_patch_hash
from app.services.git.manager import execute_git_pr_pipeline
from app.services.agent.feedback.repair_orchestrator import execute_repair_loop, MAX_REPAIR_ITERATIONS
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger("codeforge.api.agent")
router = APIRouter()


def _get_user_repository(repo_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> Repository:
    """Helper to verify repository existence and ownership."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
    if repo.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
    return repo


def _get_user_task(repo_id: uuid.UUID, task_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> AgentTask:
    """Helper to verify task existence, repository linkage, and user ownership."""
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.repository_id == repo_id
    ).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent task not found."
        )
    if task.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent task not found."
        )
    return task


@router.post(
    "/repositories/{repo_id}/agent/tasks",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def create_agent_task(
    repo_id: uuid.UUID,
    payload: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new AI Software Engineer Agent Task and launches background execution."""
    repo = _get_user_repository(repo_id, current_user.id, db)

    agent_task = AgentTask(
        user_id=current_user.id,
        repository_id=repo.id,
        task_description=payload.task,
        status="pending"
    )
    db.add(agent_task)
    db.commit()
    db.refresh(agent_task)

    from app.services.jobs import JobManager
    JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=repo.id,
        job_type="agent_task",
        task_id=agent_task.id
    )
    return agent_task


@router.get(
    "/repositories/{repo_id}/agent/tasks",
    response_model=List[AgentTaskResponse]
)
async def list_agent_tasks(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all agent tasks for a given repository."""
    _get_user_repository(repo_id, current_user.id, db)

    tasks = db.query(AgentTask).filter(
        AgentTask.repository_id == repo_id,
        AgentTask.user_id == current_user.id
    ).order_by(AgentTask.created_at.desc()).all()

    return tasks


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}",
    response_model=AgentTaskResponse
)
async def get_agent_task(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves status and details for a specific agent task."""
    return _get_user_task(repo_id, task_id, current_user.id, db)


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/plan",
    response_model=ImplementationPlanSchema
)
async def get_agent_task_plan(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the generated structured implementation plan for an agent task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    if not task.plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Implementation plan not ready yet."
        )
    return task.plan


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/changes",
    response_model=AgentTaskChangesResponse
)
async def get_agent_task_changes(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the generated code changes and unified diffs for an agent task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    changes = task.changes or []
    files_to_modify = task.files_to_modify or []
    file_changes = [FileChangeSchema(**c) for c in changes]

    return AgentTaskChangesResponse(
        task_id=task.id,
        status=task.status,
        changes=file_changes,
        files_to_modify=files_to_modify
    )


# ─── Execution Endpoints (Step 8) ──────────────────────────────────────────

@router.post(
    "/repositories/{repo_id}/agent/tasks/{task_id}/execute",
    response_model=AgentExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def execute_agent_task(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Triggers safe execution of an approved AgentTask patch inside an isolated workspace."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)

    if task.status not in ("ready_for_review", "approved", "tests_passed", "tests_failed", "execution_failed", "execution_passed", "repair_ready"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is not ready for execution. Current status: '{task.status}'."
        )

    if not task.changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has no generated code changes to execute."
        )

    execution = AgentExecution(
        task_id=task.id,
        status="pending",
        workspace_path="pending_allocation"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    from app.services.jobs import JobManager
    JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=task.repository_id,
        job_type="execution",
        task_id=task.id,
        payload={"execution_id": str(execution.id)}
    )
    return execution


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/executions",
    response_model=List[AgentExecutionResponse]
)
async def list_task_executions(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists execution history for a specific agent task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    return db.query(AgentExecution).filter(
        AgentExecution.task_id == task.id
    ).order_by(AgentExecution.created_at.desc()).all()


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/executions/{execution_id}",
    response_model=AgentExecutionResponse
)
async def get_task_execution(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves detailed execution results for a specific execution run."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)

    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id,
        AgentExecution.task_id == task.id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent execution record not found."
        )

    return execution


# ─── Git & PR Endpoints (Step 9) ──────────────────────────────────────────

@router.post(
    "/repositories/{repo_id}/agent/tasks/{task_id}/approve",
    response_model=AgentTaskResponse
)
async def approve_agent_task(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Explicitly approves the generated code changes for an agent task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)

    if not task.changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve a task without generated code changes."
        )

    repo = _get_user_repository(repo_id, current_user.id, db)
    if repo.local_path and os.path.exists(repo.local_path) and task.changes:
        try:
            from app.services.execution.patch_applier import apply_task_patch
            apply_task_patch(repo.local_path, task.changes)
            logger.info(f"Applied approved patch to local workspace '{repo.local_path}'.")
        except Exception as apply_err:
            logger.warning(f"Failed to apply approved patch to local workspace: {apply_err}")

    patch_hash = compute_patch_hash(task.changes)
    task.is_approved = True
    task.approved_patch_hash = patch_hash
    task.approved_at = datetime.datetime.now(datetime.timezone.utc)
    if task.status in ("ready_for_review", "pending", "repair_ready", "execution_passed"):
        task.status = "approved"

    db.commit()
    db.refresh(task)
    return task


@router.post(
    "/repositories/{repo_id}/agent/tasks/{task_id}/pull-request",
    response_model=GitOperationResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def create_pull_request_operation(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers Git branch creation, commit, push, and GitHub Pull Request creation.
    Requires task approval and a successful test execution.
    """
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    repo = _get_user_repository(repo_id, current_user.id, db)

    if not task.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pull Request creation requires explicit user task approval."
        )

    current_hash = compute_patch_hash(task.changes or [])
    if task.approved_patch_hash != current_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task changes have been modified since approval. Re-approval required."
        )

    exec_record = db.query(AgentExecution).filter(
        AgentExecution.task_id == task.id,
        AgentExecution.status == "passed"
    ).order_by(AgentExecution.created_at.desc()).first()

    if not exec_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pull Request creation requires at least one successful test execution."
        )

    existing_op = db.query(GitOperation).filter(
        GitOperation.task_id == task.id,
        GitOperation.status.in_(["pending", "preparing", "applying", "committing", "pushing", "creating_pr", "completed"])
    ).order_by(GitOperation.created_at.desc()).first()

    if existing_op and existing_op.status == "completed":
        return existing_op

    branch_name = f"codeforge/task-{str(task.id).split('-')[0]}"

    git_op = GitOperation(
        repository_id=repo.id,
        task_id=task.id,
        execution_id=exec_record.id,
        user_id=current_user.id,
        operation_type="pull_request",
        status="pending",
        branch_name=branch_name
    )
    db.add(git_op)
    db.commit()
    db.refresh(git_op)

    from app.services.jobs import JobManager
    JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=repo.id,
        job_type="pull_request",
        task_id=task.id,
        payload={"git_operation_id": str(git_op.id)}
    )
    return git_op


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/git-operations",
    response_model=List[GitOperationResponse]
)
async def list_git_operations(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists history of Git & PR operations for a task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    return db.query(GitOperation).filter(
        GitOperation.task_id == task.id
    ).order_by(GitOperation.created_at.desc()).all()


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/pull-request",
    response_model=GitOperationResponse
)
async def get_task_pull_request(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves current PR operation status and links for a task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    git_op = db.query(GitOperation).filter(
        GitOperation.task_id == task.id,
        GitOperation.operation_type == "pull_request"
    ).order_by(GitOperation.created_at.desc()).first()

    if not git_op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Pull Request operation found for this task."
        )

    return git_op


# ─── Feedback Loop & Repair Endpoints (Step 10) ───────────────────────────

@router.post(
    "/repositories/{repo_id}/agent/tasks/{task_id}/repair",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def start_task_repair(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Starts an autonomous feedback repair cycle for a failed execution."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)

    latest_exec = db.query(AgentExecution).filter(
        AgentExecution.task_id == task.id
    ).order_by(AgentExecution.created_at.desc()).first()

    if not latest_exec or latest_exec.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repair requires a failed test execution run."
        )

    if task.status == "repairing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repair cycle is already running for this task."
        )

    existing_iterations = db.query(AgentIteration).filter(AgentIteration.task_id == task.id).count()
    if existing_iterations >= MAX_REPAIR_ITERATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum repair iteration limit ({MAX_REPAIR_ITERATIONS}) reached. Human review required."
        )

    task.status = "repairing"
    db.commit()

    from app.services.jobs import JobManager
    JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=task.repository_id,
        job_type="repair",
        task_id=task.id
    )
    return task


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/iterations",
    response_model=List[AgentIterationResponse]
)
async def list_task_iterations(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists repair iteration history for a task."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)
    return db.query(AgentIteration).filter(
        AgentIteration.task_id == task.id
    ).order_by(AgentIteration.iteration_number.asc()).all()


@router.get(
    "/repositories/{repo_id}/agent/tasks/{task_id}/iterations/{iteration_id}",
    response_model=AgentIterationResponse
)
async def get_task_iteration(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    iteration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves detailed information for a specific repair iteration."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)

    iteration = db.query(AgentIteration).filter(
        AgentIteration.id == iteration_id,
        AgentIteration.task_id == task.id
    ).first()

    if not iteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent iteration record not found."
        )

    return iteration


@router.post(
    "/repositories/{repo_id}/agent/tasks/{task_id}/iterations/{iteration_id}/retry",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def retry_task_iteration(
    repo_id: uuid.UUID,
    task_id: uuid.UUID,
    iteration_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allows user to explicitly retry a repair iteration when limits permit."""
    task = _get_user_task(repo_id, task_id, current_user.id, db)

    existing_iterations = db.query(AgentIteration).filter(AgentIteration.task_id == task.id).count()
    if existing_iterations >= MAX_REPAIR_ITERATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum repair iteration limit ({MAX_REPAIR_ITERATIONS}) reached. Human review required."
        )

    task.status = "repairing"
    db.commit()

    from app.services.jobs import JobManager
    JobManager.enqueue_job(
        db=db,
        user_id=current_user.id,
        repository_id=task.repository_id,
        job_type="repair",
        task_id=task.id
    )
    return task
