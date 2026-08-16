"""
Comprehensive tests for CodeForge AI Step 10 AI Agent Feedback Loop & Autonomous Bug Fixing.
"""
import os
import shutil
import uuid
import pytest
import bcrypt
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import AgentTask, AgentExecution, AgentIteration
from app.schemas.agent import FileChangeSchema, RootCauseAnalysisSchema, CodeGenerationResponseSchema
from app.services.repository import RepositoryService
from app.services.agent.feedback.failure_classifier import classify_failure
from app.services.agent.feedback.repair_validator import validate_repair_patch, RepairValidationError
from app.services.agent.feedback.repair_orchestrator import execute_repair_loop, MAX_REPAIR_ITERATIONS
from tests.test_auth import create_test_token


@pytest.fixture
def feedback_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="feedback_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def auth_headers(feedback_user: User) -> dict:
    token = create_test_token(user_id=str(feedback_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def feedback_repo(db_session: Session, feedback_user: User) -> Repository:
    github_repo_id = 88776655
    workspace_path = RepositoryService.get_repository_workspace(feedback_user.id, github_repo_id)
    os.makedirs(workspace_path, exist_ok=True)

    repo = Repository(
        id=uuid.uuid4(),
        user_id=feedback_user.id,
        github_repo_id=github_repo_id,
        name="test-feedback-repo",
        full_name="feedbackuser/test-feedback-repo",
        owner="feedbackuser",
        default_branch="main",
        local_path=workspace_path,
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()

    with open(os.path.join(workspace_path, "calc.py"), "w", encoding="utf-8") as f:
        f.write("def add(a, b): return a - b\n")  # Intentional bug

    with open(os.path.join(workspace_path, "test_calc.py"), "w", encoding="utf-8") as f:
        f.write("from calc import add\ndef test_add(): assert add(2, 2) == 4\n")

    db_session.commit()
    yield repo

    if os.path.exists(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=True)


@pytest.fixture
def failed_task_and_exec(db_session: Session, feedback_user: User, feedback_repo: Repository):
    task = AgentTask(
        id=uuid.uuid4(),
        user_id=feedback_user.id,
        repository_id=feedback_repo.id,
        task_description="Fix add function bug in calc.py",
        status="execution_failed",
        changes=[{"file_path": "calc.py", "operation": "modify", "proposed_content": "def add(a, b): return a - b\n"}]
    )
    db_session.add(task)
    db_session.commit()

    exec_rec = AgentExecution(
        id=uuid.uuid4(),
        task_id=task.id,
        status="failed",
        workspace_path="dummy_exec_path",
        stdout="FAILED test_calc.py::test_add - AssertionError: assert 0 == 4",
        stderr="AssertionError: assert 0 == 4",
        test_summary={"passed": False, "tests_run": 1, "tests_passed": 0, "tests_failed": 1, "failures": ["AssertionError"]}
    )
    db_session.add(exec_rec)
    db_session.commit()

    return task, exec_rec


# ─── 1. Failure Classifier Tests ──────────────────────────────────────────

def test_failure_classification_ecosystems():
    """Classifies Python, Node, and Go failure outputs into structured categories."""
    # Pytest failure
    py_res = classify_failure(
        stdout="FAILED test_main.py::test_val - AssertionError: assert 1 == 2",
        stderr="E AssertionError: assert 1 == 2",
        test_summary={"passed": False}
    )
    assert py_res["failure_category"] == "assertion_failure"
    assert "AssertionError" in py_res["error_message"]

    # ModuleNotFoundError
    import_res = classify_failure(
        stdout="",
        stderr="ModuleNotFoundError: No module named 'nonexistent'",
        test_summary=None
    )
    assert import_res["failure_category"] == "import_error"

    # TypeScript build error
    ts_res = classify_failure(
        stdout="src/index.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.",
        stderr="",
        test_summary=None
    )
    assert ts_res["failure_category"] == "type_error"
    assert ts_res["failing_file"] == "src/index.ts"


# ─── 2. Repair Validator Safety & Anti-Cheating Tests ─────────────────────

def test_repair_validator_anti_cheating(feedback_repo: Repository):
    """Rejects patches that delete tests, skip assertions, or weaken security."""
    valid_analysis = RootCauseAnalysisSchema(
        failure_category="assertion_failure",
        root_cause="Bug in add function logic",
        confidence=0.95,
        affected_files=["calc.py"]
    )

    # 1. Low confidence rejection
    low_conf_analysis = RootCauseAnalysisSchema(
        failure_category="unknown",
        root_cause="Uncertain failure",
        confidence=0.4
    )
    with pytest.raises(RepairValidationError, match="below safe threshold"):
        validate_repair_patch([FileChangeSchema(file_path="calc.py", operation="modify", proposed_content="")], low_conf_analysis, feedback_repo.local_path)

    # 2. Test file deletion rejection
    del_test_change = FileChangeSchema(file_path="test_calc.py", operation="delete", proposed_content="")
    with pytest.raises(RepairValidationError, match="Refusing to delete test file"):
        validate_repair_patch([del_test_change], valid_analysis, feedback_repo.local_path)

    # 3. Test skip directive injection rejection
    skip_change = FileChangeSchema(
        file_path="test_calc.py",
        operation="modify",
        proposed_content="@pytest.mark.skip\ndef test_add(): pass\n"
    )
    with pytest.raises(RepairValidationError, match="Refusing repair that adds test skip directives"):
        validate_repair_patch([skip_change], valid_analysis, feedback_repo.local_path)

    # 4. Valid repair patch passes
    valid_change = FileChangeSchema(
        file_path="calc.py",
        operation="modify",
        proposed_content="def add(a, b): return a + b\n"
    )
    validate_repair_patch([valid_change], valid_analysis, feedback_repo.local_path)


# ─── 3. Repair Orchestrator & Iteration Limit Tests ───────────────────────

@pytest.mark.asyncio
async def test_repair_orchestrator_iteration_limit(db_session: Session, failed_task_and_exec):
    """Stops automatically when MAX_REPAIR_ITERATIONS (3) is exceeded and triggers human_review_required."""
    task, trigger_exec = failed_task_and_exec

    # Pre-populate 3 iterations
    for i in range(1, 4):
        db_session.add(AgentIteration(
            task_id=task.id,
            iteration_number=i,
            trigger_execution_id=trigger_exec.id,
            status="failed"
        ))
    db_session.commit()

    # Trigger 4th iteration -> must stop safely
    await execute_repair_loop(task.id, db=db_session)

    db_session.refresh(task)
    assert task.status == "human_review_required"

    iterations = db_session.query(AgentIteration).filter(AgentIteration.task_id == task.id).all()
    assert len(iterations) == 4
    assert iterations[-1].status == "stopped"
    assert "Maximum repair iteration limit reached" in iterations[-1].error_message


@pytest.mark.asyncio
async def test_repair_orchestrator_success_flow(db_session: Session, feedback_repo: Repository, failed_task_and_exec):
    """Executes a full successful repair cycle using mocked LLM and mocked execution runner."""
    task, trigger_exec = failed_task_and_exec

    with patch("app.services.agent.feedback.repair_generator.generate_code_changes") as mock_gen, \
         patch("app.services.agent.feedback.repair_orchestrator.execute_agent_task_execution_pipeline") as mock_exec:

        mock_gen.return_value = CodeGenerationResponseSchema(
            changes=[
                FileChangeSchema(
                    file_path="calc.py",
                    operation="modify",
                    proposed_content="def add(a, b): return a + b\n",
                    explanation="Fix arithmetic operation from subtraction to addition.",
                    confidence=0.98
                )
            ],
            summary="Repair patch generated"
        )

        async def fake_exec_pipeline(exec_id, db=None):
            ex = db.query(AgentExecution).filter(AgentExecution.id == exec_id).first()
            ex.status = "passed"
            ex.test_summary = {"passed": True, "tests_run": 1, "tests_passed": 1, "tests_failed": 0}
            if db:
                db.commit()

        mock_exec.side_effect = fake_exec_pipeline

        await execute_repair_loop(task.id, db=db_session)

        db_session.refresh(task)
        assert task.status == "execution_passed"
        assert task.is_approved is False  # Must remain unapproved until user explicitly reviews!

        iters = db_session.query(AgentIteration).filter(AgentIteration.task_id == task.id).all()
        assert len(iters) == 1
        assert iters[0].status == "passed"
        assert iters[0].failure_category == "assertion_failure"


# ─── 4. API Endpoints Tests ───────────────────────────────────────────────

def test_repair_api_routes(client: TestClient, auth_headers: dict, feedback_repo: Repository, failed_task_and_exec):
    """POST /repair triggers repair loop and GET /iterations lists history."""
    task, _ = failed_task_and_exec

    # Trigger repair
    resp = client.post(
        f"/api/v1/repositories/{feedback_repo.id}/agent/tasks/{task.id}/repair",
        headers=auth_headers
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "repairing"

    # List iterations
    list_resp = client.get(
        f"/api/v1/repositories/{feedback_repo.id}/agent/tasks/{task.id}/iterations",
        headers=auth_headers
    )
    assert list_resp.status_code == 200


def test_tenant_isolation_repair(client: TestClient, feedback_repo: Repository, failed_task_and_exec, db_session: Session):
    """User B receives 404 when attempting to trigger repair on User A's task."""
    task, _ = failed_task_and_exec

    user_b = User(
        id=uuid.uuid4(),
        email="userb_repair@example.com",
        hashed_password="password123",
        is_active=True
    )
    db_session.add(user_b)
    db_session.commit()

    token_b = create_test_token(user_id=str(user_b.id))
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = client.post(
        f"/api/v1/repositories/{feedback_repo.id}/agent/tasks/{task.id}/repair",
        headers=headers_b
    )
    assert resp.status_code == 404
