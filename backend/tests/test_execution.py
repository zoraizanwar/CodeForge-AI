"""
Comprehensive tests for CodeForge AI Step 8 Secure Execution & Automated Testing.
"""
import os
import shutil
import uuid
import pytest
import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import AgentTask, AgentExecution
from app.services.repository import RepositoryService, get_safe_workspace_path
from app.services.agent.validator import ChangeValidationError
from app.services.execution.workspace_manager import (
    create_execution_workspace,
    cleanup_execution_workspace,
    get_executions_base_dir
)
from app.services.execution.patch_applier import apply_task_patch
from app.services.execution.command_runner import run_sandboxed_command, get_sanitized_environment
from app.services.execution.test_detector import detect_project_and_test_commands
from app.services.execution.result_parser import (
    parse_pytest_output,
    parse_jest_output,
    parse_go_test_output,
    parse_execution_results
)
from app.services.execution.manager import execute_agent_task_execution_pipeline
from tests.test_auth import create_test_token


@pytest.fixture
def exec_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="exec_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def auth_headers(exec_user: User) -> dict:
    token = create_test_token(user_id=str(exec_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def exec_repo(db_session: Session, exec_user: User) -> Repository:
    """Fixture providing a repository with a valid local workspace."""
    github_repo_id = 987654321
    workspace_path = RepositoryService.get_repository_workspace(exec_user.id, github_repo_id)
    os.makedirs(workspace_path, exist_ok=True)

    repo = Repository(
        id=uuid.uuid4(),
        user_id=exec_user.id,
        github_repo_id=github_repo_id,
        name="test-exec-repo",
        full_name="testuser/test-exec-repo",
        owner="testuser",
        default_branch="main",
        local_path=workspace_path,
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()

    # Create dummy source files in repo workspace
    with open(os.path.join(workspace_path, "main.py"), "w", encoding="utf-8") as f:
        f.write("def main():\n    return 'OK'\n")

    with open(os.path.join(workspace_path, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest>=8.0.0\n")

    db_session.commit()
    yield repo

    if os.path.exists(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=True)


@pytest.fixture
def exec_task(db_session: Session, exec_user: User, exec_repo: Repository) -> AgentTask:
    """Fixture providing a ready_for_review AgentTask with generated changes."""
    task = AgentTask(
        id=uuid.uuid4(),
        user_id=exec_user.id,
        repository_id=exec_repo.id,
        task_description="Add test fixture in test_main.py",
        status="ready_for_review",
        changes=[
            {
                "file_path": "test_main.py",
                "operation": "create",
                "proposed_content": "def test_ok():\n    assert 1 == 1\n",
                "explanation": "Add test case",
                "confidence": 1.0,
                "diff": "+++ test_main.py\n@@ -0,0 +1,2 @@\n+def test_ok():\n+    assert 1 == 1\n"
            }
        ],
        files_to_modify=["test_main.py"]
    )
    db_session.add(task)
    db_session.commit()
    return task


# ─── 1. Workspace Isolation & Patch Application ───────────────────────────

def test_workspace_isolation_and_patch_application(exec_repo: Repository, exec_task: AgentTask):
    """Execution workspace is isolated and original repository remains unchanged."""
    exec_id = uuid.uuid4()
    target_workspace = create_execution_workspace(exec_repo.local_path, exec_id)

    assert os.path.exists(target_workspace)
    assert target_workspace != exec_repo.local_path

    # Original repo has main.py, but not test_main.py
    assert os.path.exists(os.path.join(exec_repo.local_path, "main.py"))
    assert not os.path.exists(os.path.join(exec_repo.local_path, "test_main.py"))

    # Apply patch in execution workspace
    modified = apply_task_patch(target_workspace, exec_task.changes)
    assert "test_main.py" in modified
    assert os.path.exists(os.path.join(target_workspace, "test_main.py"))

    # Crucial assertion: Original repository workspace must remain untouched!
    assert not os.path.exists(os.path.join(exec_repo.local_path, "test_main.py"))

    cleanup_execution_workspace(target_workspace)
    assert not os.path.exists(target_workspace)


# ─── 2. Patch Application Security Boundaries ────────────────────────────

def test_patch_application_security_rejections(exec_repo: Repository):
    """Rejects path traversals, absolute paths, Windows drives, UNC paths, sensitive files."""
    exec_id = uuid.uuid4()
    target_workspace = create_execution_workspace(exec_repo.local_path, exec_id)

    # Path traversal rejection
    with pytest.raises(ChangeValidationError):
        apply_task_patch(target_workspace, [{
            "file_path": "../hacked.py",
            "operation": "create",
            "proposed_content": "bad"
        }])

    # Absolute path rejection
    with pytest.raises(ChangeValidationError):
        apply_task_patch(target_workspace, [{
            "file_path": "/etc/passwd",
            "operation": "create",
            "proposed_content": "bad"
        }])

    # Windows drive letter rejection
    with pytest.raises(ChangeValidationError):
        apply_task_patch(target_workspace, [{
            "file_path": "C:\\Windows\\System32\\cmd.exe",
            "operation": "create",
            "proposed_content": "bad"
        }])

    # Sensitive file rejection (.env)
    with pytest.raises(ChangeValidationError):
        apply_task_patch(target_workspace, [{
            "file_path": ".env",
            "operation": "create",
            "proposed_content": "SECRET_KEY=123"
        }])

    cleanup_execution_workspace(target_workspace)


# ─── 3. Command Runner & Environment Secret Sanitization ──────────────────

@pytest.mark.asyncio
async def test_command_runner_sanitizes_environment():
    """Verifies host secrets are stripped from subprocess environment."""
    os.environ["GROK_API_KEY"] = "secret-grok-key-123"
    os.environ["JWT_SECRET_KEY"] = "secret-jwt-key-456"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

    clean_env = get_sanitized_environment()

    assert "GROK_API_KEY" not in clean_env
    assert "JWT_SECRET_KEY" not in clean_env
    assert "DATABASE_URL" not in clean_env
    assert "PATH" in clean_env


@pytest.mark.asyncio
async def test_command_runner_execution(exec_repo: Repository):
    """Runs a sandboxed command and captures exit code, stdout, and stderr."""
    res = await run_sandboxed_command(["python", "-c", "print('hello from sandbox')"], cwd=exec_repo.local_path)
    assert res.exit_code == 0
    assert "hello from sandbox" in res.stdout
    assert res.duration_seconds >= 0.0


# ─── 4. Project & Test Detection ──────────────────────────────────────────

def test_project_detection(exec_repo: Repository):
    """Detects Python project with pip and pytest."""
    config = detect_project_and_test_commands(exec_repo.local_path)
    assert config.language == "python"
    assert config.package_manager == "pip"
    assert len(config.test_commands) >= 1
    assert "python" in config.test_commands[0][0] or "pytest" in config.test_commands[0][-1]


# ─── 5. Test Result Parsing ───────────────────────────────────────────────

def test_result_parsers():
    """Parses pytest, Jest, and Go test output into standardized summaries."""
    pytest_out = "================ 21 passed, 2 warnings in 8.84s ================"
    py_res = parse_pytest_output(pytest_out)
    assert py_res["tests_passed"] == 21
    assert py_res["tests_failed"] == 0

    jest_out = "Tests: 5 passed, 1 failed, 6 total"
    jest_res = parse_jest_output(jest_out)
    assert jest_res["tests_passed"] == 5
    assert jest_res["tests_failed"] == 1

    go_out = "--- PASS: TestFoo (0.01s)\n--- FAIL: TestBar (0.02s)"
    go_res = parse_go_test_output(go_out)
    assert go_res["tests_passed"] == 1
    assert go_res["tests_failed"] == 1


# ─── 6. Full Execution Pipeline End-to-End ─────────────────────────────────

@pytest.mark.asyncio
async def test_full_execution_pipeline(db_session: Session, exec_task: AgentTask):
    """Runs the execution manager pipeline from pending -> passed/failed."""
    execution = AgentExecution(
        id=uuid.uuid4(),
        task_id=exec_task.id,
        status="pending",
        workspace_path="pending"
    )
    db_session.add(execution)
    db_session.commit()

    await execute_agent_task_execution_pipeline(execution.id, db=db_session)

    db_session.refresh(execution)
    db_session.refresh(exec_task)

    assert execution.status in ("passed", "failed")
    assert execution.command_results is not None
    assert execution.test_summary is not None
    assert exec_task.status in ("tests_passed", "tests_failed")


# ─── 7. API Endpoint Verification ─────────────────────────────────────────

def test_execute_api_requires_auth(client: TestClient, exec_repo: Repository, exec_task: AgentTask):
    """POST /execute requires authentication."""
    resp = client.post(f"/api/v1/repositories/{exec_repo.id}/agent/tasks/{exec_task.id}/execute")
    assert resp.status_code == 401


def test_execute_api_flow(client: TestClient, auth_headers: dict, exec_repo: Repository, exec_task: AgentTask):
    """POST /execute triggers 202 Accepted and creates AgentExecution."""
    resp = client.post(
        f"/api/v1/repositories/{exec_repo.id}/agent/tasks/{exec_task.id}/execute",
        headers=auth_headers
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] in ("pending", "preparing")
    assert data["task_id"] == str(exec_task.id)

    # Get execution history
    hist_resp = client.get(
        f"/api/v1/repositories/{exec_repo.id}/agent/tasks/{exec_task.id}/executions",
        headers=auth_headers
    )
    assert hist_resp.status_code == 200
    exec_list = hist_resp.json()
    assert len(exec_list) >= 1


def test_execute_api_rejects_pending_task(client: TestClient, auth_headers: dict, exec_repo: Repository, exec_user: User, db_session: Session):
    """Rejects execution if task is not in ready_for_review state."""
    pending_task = AgentTask(
        id=uuid.uuid4(),
        user_id=exec_user.id,
        repository_id=exec_repo.id,
        task_description="Pending task",
        status="pending"
    )
    db_session.add(pending_task)
    db_session.commit()

    resp = client.post(
        f"/api/v1/repositories/{exec_repo.id}/agent/tasks/{pending_task.id}/execute",
        headers=auth_headers
    )
    assert resp.status_code == 400
    assert "Task is not ready for execution" in resp.json()["detail"]


def test_tenant_isolation_executions(client: TestClient, exec_repo: Repository, exec_task: AgentTask, db_session: Session):
    """User B receives 404 when accessing User A's task executions."""
    user_b = User(
        id=uuid.uuid4(),
        email="userb_exec@example.com",
        hashed_password="password123",
        is_active=True
    )
    db_session.add(user_b)
    db_session.commit()

    token_b = create_test_token(user_id=str(user_b.id))
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = client.post(
        f"/api/v1/repositories/{exec_repo.id}/agent/tasks/{exec_task.id}/execute",
        headers=headers_b
    )
    assert resp.status_code == 404
