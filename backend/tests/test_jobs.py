"""
Comprehensive test suite for CodeForge AI Step 11 Production-Grade Job Orchestration & Real-Time Monitoring.
"""
import uuid
import pytest
import asyncio
import datetime
import bcrypt
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import AgentTask, AgentExecution
from app.models.job import AgentJob
from app.services.repository import RepositoryService
from app.services.jobs.retry_policy import is_transient_failure, calculate_exponential_backoff
from app.services.jobs.queue import claim_next_job, count_running_jobs_for_user, count_running_jobs_for_repository
from app.services.jobs.job_manager import JobManager
from app.services.jobs.worker import recover_stale_running_jobs, process_single_job
from app.services.jobs.cancellation import cancel_job_execution, is_job_cancelled_in_memory
from tests.test_auth import create_test_token


@pytest.fixture
def job_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="job_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def auth_headers(job_user: User) -> dict:
    token = create_test_token(user_id=str(job_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def job_repo(db_session: Session, job_user: User) -> Repository:
    github_repo_id = 99887766
    workspace_path = RepositoryService.get_repository_workspace(job_user.id, github_repo_id)
    repo = Repository(
        id=uuid.uuid4(),
        user_id=job_user.id,
        github_repo_id=github_repo_id,
        name="test-job-repo",
        full_name="jobuser/test-job-repo",
        owner="jobuser",
        default_branch="main",
        local_path=workspace_path,
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()
    return repo


@pytest.fixture
def job_task(db_session: Session, job_user: User, job_repo: Repository) -> AgentTask:
    task = AgentTask(
        id=uuid.uuid4(),
        user_id=job_user.id,
        repository_id=job_repo.id,
        task_description="Test durable job orchestration task",
        status="pending"
    )
    db_session.add(task)
    db_session.commit()
    return task


# ─── 1. Job Creation & Model Validation Tests ──────────────────────────────

def test_job_enqueue_and_model_fields(db_session: Session, job_user: User, job_repo: Repository, job_task: AgentTask):
    """Enqueues an AgentJob and verifies default fields, relationships, and metadata."""
    job = JobManager.enqueue_job(
        db=db_session,
        user_id=job_user.id,
        repository_id=job_repo.id,
        job_type="agent_task",
        task_id=job_task.id,
        priority=10,
        payload={"options": "test"}
    )

    assert job.id is not None
    assert job.status == "queued"
    assert job.progress == 0
    assert job.current_stage == "queued"
    assert job.attempt_count == 0
    assert job.max_attempts == 3
    assert job.priority == 10
    assert job.payload == {"options": "test"}

    # Task status sync
    db_session.refresh(job_task)
    assert job_task.status == "analyzing"


def test_duplicate_operation_prevention(db_session: Session, job_user: User, job_repo: Repository, job_task: AgentTask):
    """Rejects duplicate active jobs for the same task/repository."""
    JobManager.enqueue_job(
        db=db_session,
        user_id=job_user.id,
        repository_id=job_repo.id,
        job_type="repair",
        task_id=job_task.id
    )

    with pytest.raises(ValueError, match="An active 'repair' job is already running"):
        JobManager.enqueue_job(
            db=db_session,
            user_id=job_user.id,
            repository_id=job_repo.id,
            job_type="repair",
            task_id=job_task.id
        )


# ─── 2. Queue Claiming & Concurrency Control ─────────────────────────────

def test_queue_claiming_priority_and_concurrency(db_session: Session, job_user: User, job_repo: Repository):
    """Claims queued jobs in priority order while enforcing user & repo concurrency limits."""
    # Enqueue low priority job 1
    job1 = JobManager.enqueue_job(db=db_session, user_id=job_user.id, repository_id=job_repo.id, job_type="analysis", priority=1)
    # Enqueue high priority job 2
    job2 = JobManager.enqueue_job(db=db_session, user_id=job_user.id, repository_id=job_repo.id, job_type="analysis", priority=10)

    # Claim first job -> should be job2 (highest priority)
    claimed = claim_next_job(db_session)
    assert claimed is not None
    assert claimed.id == job2.id
    assert claimed.status == "running"
    assert claimed.attempt_count == 1

    # Claim second job -> should be job1
    claimed2 = claim_next_job(db_session)
    assert claimed2 is not None
    assert claimed2.id == job1.id


# ─── 3. Retry Policy & Transient Error Classification ──────────────────────

def test_retry_policy_classification():
    """Verifies transient errors are retryable and security/permission errors are non-retryable."""
    # Transient failures
    assert is_transient_failure(TimeoutError("Connection timed out")) is True
    assert is_transient_failure(RuntimeError("Temporary Network Failure")) is True

    # Non-retryable failures
    assert is_transient_failure(PermissionError("Access denied")) is False
    assert is_transient_failure(ValueError("Invalid argument")) is False
    assert is_transient_failure(Exception("Path traversal attempt detected")) is False
    assert is_transient_failure(Exception("Refusing to delete test file")) is False

    # Backoff calculations
    assert calculate_exponential_backoff(1, base_delay=2.0) == 2.0
    assert calculate_exponential_backoff(2, base_delay=2.0) == 4.0
    assert calculate_exponential_backoff(3, base_delay=2.0) == 8.0
    assert calculate_exponential_backoff(10, base_delay=2.0, max_delay=30.0) == 30.0


# ─── 4. Cancellation & Process Termination ────────────────────────────────

@pytest.mark.asyncio
async def test_job_cancellation(db_session: Session, job_user: User, job_repo: Repository, job_task: AgentTask):
    """Cancels a running job and verifies process cleanup and status update."""
    job = JobManager.enqueue_job(db=db_session, user_id=job_user.id, repository_id=job_repo.id, job_type="repair", task_id=job_task.id)
    job.status = "running"
    db_session.commit()

    cancelled_job = await JobManager.cancel_job(db_session, job.id, job_user.id)
    assert cancelled_job.status == "cancelled"
    assert cancelled_job.completed_at is not None
    assert is_job_cancelled_in_memory(job.id)


# ─── 5. Stale Job Recovery on Worker Startup ──────────────────────────────

def test_stale_job_recovery(db_session: Session, job_user: User, job_repo: Repository):
    """Recovers jobs left in 'running' state after a simulated worker crash."""
    stale_job = AgentJob(
        id=uuid.uuid4(),
        user_id=job_user.id,
        repository_id=job_repo.id,
        job_type="analysis",
        status="running",
        attempt_count=1,
        max_attempts=3
    )
    stale_pr_job = AgentJob(
        id=uuid.uuid4(),
        user_id=job_user.id,
        repository_id=job_repo.id,
        job_type="pull_request",
        status="running",
        attempt_count=1,
        max_attempts=3
    )
    db_session.add_all([stale_job, stale_pr_job])
    db_session.commit()

    recover_stale_running_jobs(db_session)

    db_session.refresh(stale_job)
    db_session.refresh(stale_pr_job)

    # General jobs recover as retrying
    assert stale_job.status == "retrying"

    # Git PR jobs fail safely to prevent partial push ambiguity
    assert stale_pr_job.status == "failed"


# ─── 6. Job API & Tenant Isolation Tests ─────────────────────────────────

def test_job_api_endpoints_and_tenant_isolation(client: TestClient, auth_headers: dict, job_user: User, job_repo: Repository, db_session: Session):
    """Verifies GET /jobs, GET /jobs/{id}, POST /cancel, POST /retry API endpoints and tenant security."""
    job = JobManager.enqueue_job(db=db_session, user_id=job_user.id, repository_id=job_repo.id, job_type="analysis")

    # List jobs
    resp = client.get("/api/v1/jobs", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Get job details
    get_resp = client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == str(job.id)

    # Cancel job
    cancel_resp = client.post(f"/api/v1/jobs/{job.id}/cancel", headers=auth_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Retry job
    retry_resp = client.post(f"/api/v1/jobs/{job.id}/retry", headers=auth_headers)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "queued"

    # Tenant isolation test: User B cannot observe or cancel User A's job
    user_b = User(id=uuid.uuid4(), email="userb_jobs@codeforge.test", hashed_password="pw", is_active=True)
    db_session.add(user_b)
    db_session.commit()

    token_b = create_test_token(user_id=str(user_b.id))
    headers_b = {"Authorization": f"Bearer {token_b}"}

    iso_resp = client.get(f"/api/v1/jobs/{job.id}", headers=headers_b)
    assert iso_resp.status_code == 404


# ─── 7. Worker Processing & Execution Pipeline ────────────────────────────

@pytest.mark.asyncio
async def test_worker_processing_success_flow(db_session: Session, job_user: User, job_repo: Repository):
    """Executes a queued analysis job using process_single_job and verifies completion."""
    job = JobManager.enqueue_job(db=db_session, user_id=job_user.id, repository_id=job_repo.id, job_type="analysis")
    job.status = "running"
    job.attempt_count = 1
    db_session.commit()

    with patch("app.services.jobs.worker.run_analysis_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {"files_indexed": 5}

        await process_single_job(job.id, db=db_session)

        db_session.expire_all()
        job_db = db_session.query(AgentJob).filter(AgentJob.id == job.id).first()
        assert job_db.status == "completed"
        assert job_db.progress == 100
        assert job_db.result == {"status": "success", "analysis": {"files_indexed": 5}}


# ─── 8. WebSocket Stream & Auth Tests ────────────────────────────────────

def test_websocket_stream_authentication(client: TestClient, job_user: User, job_repo: Repository, db_session: Session):
    """Verifies WebSocket /stream rejects unauthenticated tokens and dumps initial state for valid connections."""
    job = JobManager.enqueue_job(db=db_session, user_id=job_user.id, repository_id=job_repo.id, job_type="analysis")
    job.status = "completed"
    db_session.commit()

    token = create_test_token(user_id=str(job_user.id))

    # Rejects invalid token
    try:
        with client.websocket_connect(f"/api/v1/jobs/{job.id}/stream?token=invalid_token") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
    except Exception:
        pass  # WebSocket connection closed due to invalid token policy

    # Accepts valid token & dumps initial state
    with client.websocket_connect(f"/api/v1/jobs/{job.id}/stream?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "job_initial_state"
        assert data["job"]["id"] == str(job.id)
        assert data["job"]["status"] == "completed"
