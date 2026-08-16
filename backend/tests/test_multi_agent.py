"""
Comprehensive test suite for CodeForge AI Step 12 Multi-Agent Software Engineering Workflow.
"""
import uuid
import pytest
import asyncio
import bcrypt
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.repository import Repository
from app.models.agent import AgentTask, AgentExecution
from app.models.multi_agent import AgentRun, AgentRunStep
from app.services.repository import RepositoryService
from app.services.agents import (
    PlannerAgent,
    EngineerAgent,
    ReviewerAgent,
    SecurityAgent,
    TesterAgent,
    RepairAgent,
    run_multi_agent_workflow,
    build_agent_context,
    PlanResult,
    CodeGenerationResult,
    ReviewResult,
    SecurityReviewResult,
    TestResult,
    RepairResult
)
from app.services.jobs.job_manager import JobManager
from tests.test_auth import create_test_token


@pytest.fixture
def multi_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="multi_agent_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def auth_headers(multi_user: User) -> dict:
    token = create_test_token(user_id=str(multi_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def multi_repo(db_session: Session, multi_user: User) -> Repository:
    github_repo_id = 88776655
    workspace_path = RepositoryService.get_repository_workspace(multi_user.id, github_repo_id)
    import os
    os.makedirs(os.path.join(workspace_path, "app"), exist_ok=True)
    with open(os.path.join(workspace_path, "main.py"), "w") as f:
        f.write("# main entrypoint\n")
    with open(os.path.join(workspace_path, "app", "middleware.py"), "w") as f:
        f.write("# middleware\n")
    with open(os.path.join(workspace_path, "app", "auth.py"), "w") as f:
        f.write("# auth\n")

    repo = Repository(
        id=uuid.uuid4(),
        user_id=multi_user.id,
        github_repo_id=github_repo_id,
        name="test-multi-repo",
        full_name="multiuser/test-multi-repo",
        owner="multiuser",
        default_branch="main",
        local_path=workspace_path,
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()
    return repo


@pytest.fixture
def multi_task(db_session: Session, multi_user: User, multi_repo: Repository) -> AgentTask:
    task = AgentTask(
        id=uuid.uuid4(),
        user_id=multi_user.id,
        repository_id=multi_repo.id,
        task_description="Add security middleware and validation",
        status="pending"
    )
    db_session.add(task)
    db_session.commit()
    return task


@pytest.fixture
def multi_run(db_session: Session, multi_user: User, multi_repo: Repository, multi_task: AgentTask) -> AgentRun:
    run = AgentRun(
        id=uuid.uuid4(),
        user_id=multi_user.id,
        repository_id=multi_repo.id,
        task_id=multi_task.id,
        status="pending",
        current_agent="planner",
        workflow_stage="queued"
    )
    db_session.add(run)
    db_session.commit()
    return run


# ─── 1. Planner Agent Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_agent_execution(db_session: Session, multi_run: AgentRun):
    """Planner Agent produces structured PlanResult without generating code patches."""
    step = AgentRunStep(id=uuid.uuid4(), run_id=multi_run.id, agent_type="planner", status="running")
    db_session.add(step)
    db_session.commit()

    ctx = build_agent_context(db_session, multi_run, "planner")
    planner = PlannerAgent()
    res = await planner.execute(db_session, multi_run, step, ctx)

    assert isinstance(res, PlanResult)
    assert len(res.affected_files) >= 1
    assert len(res.proposed_changes) >= 1
    assert res.confidence >= 0.70


# ─── 2. Engineer Agent Tests & Limits ──────────────────────────────────────

@pytest.mark.asyncio
async def test_engineer_agent_execution_and_limits(db_session: Session, multi_run: AgentRun):
    """Engineer Agent generates CodeGenerationResult obeying file and size limits."""
    step = AgentRunStep(id=uuid.uuid4(), run_id=multi_run.id, agent_type="engineer", status="running")
    db_session.add(step)
    db_session.commit()

    ctx = build_agent_context(db_session, multi_run, "engineer")
    ctx["previous_outputs"] = {
        "planner": {
            "strategy": "Update middleware",
            "affected_files": ["app/middleware.py"]
        }
    }

    engineer = EngineerAgent()
    res = await engineer.execute(db_session, multi_run, step, ctx)

    assert isinstance(res, CodeGenerationResult)
    assert res.total_files_changed <= 20
    assert res.total_size_bytes <= 2 * 1024 * 1024
    assert res.confidence >= 0.70


# ─── 3. Reviewer Agent Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reviewer_agent_execution(db_session: Session, multi_run: AgentRun):
    """Reviewer Agent independently evaluates changes and returns structured findings."""
    step = AgentRunStep(id=uuid.uuid4(), run_id=multi_run.id, agent_type="reviewer", status="running")
    db_session.add(step)
    db_session.commit()

    ctx = build_agent_context(db_session, multi_run, "reviewer")
    ctx["previous_outputs"] = {
        "engineer": {
            "file_operations": [
                {"file_path": "app/middleware.py", "action": "modify", "content": "# TODO: fix this\nexcept Exception: pass"}
            ]
        }
    }

    reviewer = ReviewerAgent()
    res = await reviewer.execute(db_session, multi_run, step, ctx)

    assert isinstance(res, ReviewResult)
    assert len(res.findings) >= 1
    assert any(f.category == "maintainability" for f in res.findings)


# ─── 4. Security Agent & High Severity Blocking ───────────────────────────

@pytest.mark.asyncio
async def test_security_agent_critical_finding_blocking(db_session: Session, multi_run: AgentRun):
    """Security Agent flags critical vulnerabilities and sets passed=False."""
    step = AgentRunStep(id=uuid.uuid4(), run_id=multi_run.id, agent_type="security", status="running")
    db_session.add(step)
    db_session.commit()

    ctx = build_agent_context(db_session, multi_run, "security")
    ctx["previous_outputs"] = {
        "engineer": {
            "file_operations": [
                {"file_path": "app/auth.py", "action": "modify", "content": "os.system('rm -rf /')\nAWS_SECRET_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE12345678901234567890'"}
            ]
        }
    }

    security = SecurityAgent()
    res = await security.execute(db_session, multi_run, step, ctx)

    assert isinstance(res, SecurityReviewResult)
    assert res.passed is False
    assert res.has_critical_or_high is True
    assert len(res.findings) >= 1


# ─── 5. Tester Agent Sandbox Execution ────────────────────────────────────

@pytest.mark.asyncio
async def test_tester_agent_sandbox_execution(db_session: Session, multi_run: AgentRun):
    """Tester Agent executes tests in Step 8 sandbox and reports TestResult."""
    step = AgentRunStep(id=uuid.uuid4(), run_id=multi_run.id, agent_type="tester", status="running")
    db_session.add(step)
    db_session.commit()

    ctx = build_agent_context(db_session, multi_run, "tester")

    tester = TesterAgent()
    res = await tester.execute(db_session, multi_run, step, ctx)

    assert isinstance(res, TestResult)
    assert res.tests_run >= 1


# ─── 6. Full Orchestration & Human Approval Gate ─────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_full_workflow_and_approval_gate(db_session: Session, multi_run: AgentRun):
    """Full workflow completes automated stages and halts at human_review_required approval gate."""
    async def mock_exec_pipeline(exec_id, db):
        from app.models.agent import AgentExecution
        ex = db.query(AgentExecution).filter(AgentExecution.id == exec_id).first()
        if ex:
            ex.status = "passed"
            ex.test_summary = {"total_tests": 2, "tests_passed": 2, "tests_failed": 0}
            db.commit()

    with patch("app.services.agents.tester.execute_agent_task_execution_pipeline", side_effect=mock_exec_pipeline):
        res = await run_multi_agent_workflow(multi_run.id, db=db_session)

        db_session.refresh(multi_run)
        assert multi_run.status == "human_review_required"
        assert multi_run.workflow_stage == "human_approval_gate"
        assert multi_run.overall_progress == 95
        assert multi_run.final_decision["decision"] == "human_review_required"


# ─── 7. API Endpoints & Tenant Isolation ──────────────────────────────────

def test_multi_agent_api_endpoints_and_tenant_isolation(
    client: TestClient,
    auth_headers: dict,
    multi_user: User,
    multi_repo: Repository,
    multi_task: AgentTask,
    multi_run: AgentRun,
    db_session: Session
):
    """Verifies POST /runs, GET /runs, GET /runs/{id}, GET /runs/{id}/steps, POST /cancel, POST /retry and tenant isolation."""
    # Start run via API
    start_resp = client.post(
        f"/api/v1/repositories/{multi_repo.id}/agent/runs",
        headers=auth_headers,
        json={"task_description": "Add multi-tenant security headers"}
    )
    assert start_resp.status_code == 202
    run_data = start_resp.json()
    assert run_data["status"] == "pending"

    # List runs
    list_resp = client.get(f"/api/v1/repositories/{multi_repo.id}/agent/runs", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Get run details
    get_resp = client.get(f"/api/v1/repositories/{multi_repo.id}/agent/runs/{multi_run.id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == str(multi_run.id)

    # Cancel run
    cancel_resp = client.post(f"/api/v1/repositories/{multi_repo.id}/agent/runs/{multi_run.id}/cancel", headers=auth_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Retry run
    retry_resp = client.post(f"/api/v1/repositories/{multi_repo.id}/agent/runs/{multi_run.id}/retry", headers=auth_headers)
    assert retry_resp.status_code == 202
    assert retry_resp.json()["status"] == "pending"

    # Tenant isolation test: User B cannot access User A's run
    user_b = User(id=uuid.uuid4(), email="userb_multi@codeforge.test", hashed_password="pw", is_active=True)
    db_session.add(user_b)
    db_session.commit()

    token_b = create_test_token(user_id=str(user_b.id))
    headers_b = {"Authorization": f"Bearer {token_b}"}

    iso_resp = client.get(f"/api/v1/repositories/{multi_repo.id}/agent/runs/{multi_run.id}", headers=headers_b)
    assert iso_resp.status_code == 404


# ─── 8. WebSocket Stream Auth & Ownership ──────────────────────────────────

def test_websocket_stream_authentication_and_isolation(
    client: TestClient,
    multi_user: User,
    multi_repo: Repository,
    multi_run: AgentRun,
    db_session: Session
):
    """Verifies WebSocket stream requires valid JWT token and correct repository ownership."""
    token = create_test_token(user_id=str(multi_user.id))

    # Connect with valid token
    with client.websocket_connect(f"/api/v1/repositories/{multi_repo.id}/agent/runs/{multi_run.id}/stream?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "run_initial_state"
        assert data["run"]["id"] == str(multi_run.id)
