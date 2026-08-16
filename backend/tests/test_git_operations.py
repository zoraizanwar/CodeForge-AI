"""
Comprehensive tests for CodeForge AI Step 9 Git Branch Management & GitHub PR Automation.
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
from app.models.github import GitHubInstallation
from app.models.agent import AgentTask, AgentExecution, GitOperation
from app.services.repository import RepositoryService
from app.services.git.branch_manager import validate_branch_name, generate_feature_branch_name, BranchValidationError
from app.services.git.commit_manager import format_commit_message, verify_commit_files_safety, CommitValidationError
from app.services.git.patch_fingerprint import compute_patch_hash
from app.services.git.manager import execute_git_pr_pipeline
from tests.test_auth import create_test_token


@pytest.fixture
def git_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="git_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.flush()

    # Add mock GitHub installation
    inst = GitHubInstallation(
        id=uuid.uuid4(),
        user_id=u.id,
        installation_id=12345678,
        github_account_id=87654321,
        github_account_login="git_user",
        github_account_type="User"
    )
    db_session.add(inst)
    db_session.commit()
    return u


@pytest.fixture
def auth_headers(git_user: User) -> dict:
    token = create_test_token(user_id=str(git_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def git_repo(db_session: Session, git_user: User) -> Repository:
    github_repo_id = 99887766
    workspace_path = RepositoryService.get_repository_workspace(git_user.id, github_repo_id)
    os.makedirs(workspace_path, exist_ok=True)

    repo = Repository(
        id=uuid.uuid4(),
        user_id=git_user.id,
        github_repo_id=github_repo_id,
        name="test-git-repo",
        full_name="gituser/test-git-repo",
        owner="gituser",
        default_branch="main",
        local_path=workspace_path,
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()

    # Dummy file
    with open(os.path.join(workspace_path, "main.py"), "w", encoding="utf-8") as f:
        f.write("def main(): pass\n")

    db_session.commit()
    yield repo

    if os.path.exists(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=True)


@pytest.fixture
def approved_task(db_session: Session, git_user: User, git_repo: Repository) -> AgentTask:
    changes = [
        {
            "file_path": "feature.py",
            "operation": "create",
            "proposed_content": "def feature(): return 42\n"
        }
    ]
    p_hash = compute_patch_hash(changes)
    task = AgentTask(
        id=uuid.uuid4(),
        user_id=git_user.id,
        repository_id=git_repo.id,
        task_description="Add new feature.py implementation",
        status="approved",
        is_approved=True,
        approved_patch_hash=p_hash,
        changes=changes,
        files_to_modify=["feature.py"]
    )
    db_session.add(task)
    db_session.commit()
    return task


@pytest.fixture
def passed_execution(db_session: Session, approved_task: AgentTask) -> AgentExecution:
    exec_rec = AgentExecution(
        id=uuid.uuid4(),
        task_id=approved_task.id,
        status="passed",
        workspace_path="dummy_exec_path",
        test_summary={"passed": True, "tests_run": 5, "tests_passed": 5, "duration_seconds": 1.5}
    )
    db_session.add(exec_rec)
    db_session.commit()
    return exec_rec


# ─── 1. Branch Name Security Validation ───────────────────────────────────

def test_branch_name_validation():
    """Branch manager rejects default branches, hyphens, and traversal syntax."""
    # Valid feature branch
    assert validate_branch_name("codeforge/task-12345678") == "codeforge/task-12345678"

    # Protected branch rejections
    with pytest.raises(BranchValidationError):
        validate_branch_name("main")

    with pytest.raises(BranchValidationError):
        validate_branch_name("master")

    with pytest.raises(BranchValidationError):
        validate_branch_name("develop")

    with pytest.raises(BranchValidationError):
        validate_branch_name("production")

    with pytest.raises(BranchValidationError):
        validate_branch_name("main/sub")

    # Syntax rejections
    with pytest.raises(BranchValidationError):
        validate_branch_name("-invalid-start")

    with pytest.raises(BranchValidationError):
        validate_branch_name("branch..traversal")

    with pytest.raises(BranchValidationError):
        validate_branch_name("branch with spaces")


def test_feature_branch_generation():
    """Generates standardized feature branch name."""
    t_id = uuid.uuid4()
    branch = generate_feature_branch_name(t_id)
    assert branch.startswith("codeforge/task-")
    assert str(t_id).split("-")[0] in branch


# ─── 2. Commit Message & File Safety ──────────────────────────────────────

def test_commit_message_and_file_safety():
    """Formats commit message and rejects sensitive file commits."""
    msg = format_commit_message("Fix user authentication overflow bug in auth service")
    assert msg.startswith("CodeForge: Fix user authentication overflow bug")

    # File safety checks
    verify_commit_files_safety(["main.py", "app/routes.py"])

    with pytest.raises(CommitValidationError):
        verify_commit_files_safety([".env"])

    with pytest.raises(CommitValidationError):
        verify_commit_files_safety(["config/secret.pem"])


# ─── 3. Patch Fingerprint Matcher ─────────────────────────────────────────

def test_patch_fingerprint():
    """Patch fingerprint is deterministic and order-independent for files."""
    c1 = [{"file_path": "a.py", "operation": "create", "proposed_content": "A"}]
    c2 = [{"file_path": "a.py", "operation": "create", "proposed_content": "A"}]
    c3 = [{"file_path": "a.py", "operation": "create", "proposed_content": "B"}]

    assert compute_patch_hash(c1) == compute_patch_hash(c2)
    assert compute_patch_hash(c1) != compute_patch_hash(c3)


# ─── 4. End-to-End Pipeline Mock Execution ─────────────────────────────────

@pytest.mark.asyncio
async def test_full_git_pr_pipeline_mocked(db_session: Session, git_repo: Repository, approved_task: AgentTask, passed_execution: AgentExecution):
    """Executes full Git & PR creation pipeline with mocked Git and GitHub API calls."""
    git_op = GitOperation(
        id=uuid.uuid4(),
        repository_id=git_repo.id,
        task_id=approved_task.id,
        user_id=git_repo.user_id,
        operation_type="pull_request",
        status="pending",
        branch_name=f"codeforge/task-{str(approved_task.id).split('-')[0]}"
    )
    db_session.add(git_op)
    db_session.commit()

    with patch("app.services.execution.command_runner.run_sandboxed_command") as mock_run, \
         patch("app.services.github.GitHubService.get_installation_access_token") as mock_token, \
         patch("app.services.git.manager.push_feature_branch_to_remote") as mock_push, \
         patch("app.services.github.pr_service.GitHubPRService.create_pull_request") as mock_pr:

        mock_run.return_value = MagicMock(exit_code=0, stdout="abc123456789\n", stderr="")
        mock_token.return_value = "ghs_mock_token_123"
        mock_push.return_value = "codeforge/task-123"
        mock_pr.return_value = {
            "number": 42,
            "html_url": "https://github.com/gituser/test-git-repo/pull/42"
        }

        await execute_git_pr_pipeline(git_op.id, db=db_session)

        db_session.refresh(git_op)
        db_session.refresh(approved_task)

        assert git_op.status == "completed"
        assert git_op.pull_request_number == 42
        assert git_op.pull_request_url == "https://github.com/gituser/test-git-repo/pull/42"
        assert approved_task.status == "pr_created"


# ─── 5. API Endpoints Tests ───────────────────────────────────────────────

def test_approve_api_route(client: TestClient, auth_headers: dict, git_repo: Repository, db_session: Session, git_user: User):
    """POST /approve marks task approved and records patch fingerprint."""
    task = AgentTask(
        id=uuid.uuid4(),
        user_id=git_user.id,
        repository_id=git_repo.id,
        task_description="Task for approval",
        status="ready_for_review",
        changes=[{"file_path": "new.py", "operation": "create", "proposed_content": "val"}]
    )
    db_session.add(task)
    db_session.commit()

    resp = client.post(
        f"/api/v1/repositories/{git_repo.id}/agent/tasks/{task.id}/approve",
        headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_approved"] is True
    assert data["approved_patch_hash"] is not None
    assert data["status"] == "approved"


def test_pull_request_api_requires_approval(client: TestClient, auth_headers: dict, git_repo: Repository, db_session: Session, git_user: User):
    """POST /pull-request rejects if task is unapproved."""
    unapproved_task = AgentTask(
        id=uuid.uuid4(),
        user_id=git_user.id,
        repository_id=git_repo.id,
        task_description="Unapproved task",
        status="ready_for_review",
        is_approved=False,
        changes=[{"file_path": "new.py", "operation": "create", "proposed_content": "val"}]
    )
    db_session.add(unapproved_task)
    db_session.commit()

    resp = client.post(
        f"/api/v1/repositories/{git_repo.id}/agent/tasks/{unapproved_task.id}/pull-request",
        headers=auth_headers
    )
    assert resp.status_code == 400
    assert "requires explicit user task approval" in resp.json()["detail"]


def test_pull_request_api_requires_passed_execution(client: TestClient, auth_headers: dict, git_repo: Repository, approved_task: AgentTask):
    """POST /pull-request rejects if no successful test execution exists."""
    resp = client.post(
        f"/api/v1/repositories/{git_repo.id}/agent/tasks/{approved_task.id}/pull-request",
        headers=auth_headers
    )
    assert resp.status_code == 400
    assert "requires at least one successful test execution" in resp.json()["detail"]


def test_pull_request_api_flow(client: TestClient, auth_headers: dict, git_repo: Repository, approved_task: AgentTask, passed_execution: AgentExecution):
    """POST /pull-request triggers 202 Accepted when task is approved and execution passed."""
    resp = client.post(
        f"/api/v1/repositories/{git_repo.id}/agent/tasks/{approved_task.id}/pull-request",
        headers=auth_headers
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["operation_type"] == "pull_request"

    # Get Git operations history
    hist_resp = client.get(
        f"/api/v1/repositories/{git_repo.id}/agent/tasks/{approved_task.id}/git-operations",
        headers=auth_headers
    )
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) >= 1


def test_tenant_isolation_git_operations(client: TestClient, git_repo: Repository, approved_task: AgentTask, db_session: Session):
    """User B receives 404 when accessing User A's PR endpoints."""
    user_b = User(
        id=uuid.uuid4(),
        email="userb_git@example.com",
        hashed_password="password123",
        is_active=True
    )
    db_session.add(user_b)
    db_session.commit()

    token_b = create_test_token(user_id=str(user_b.id))
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = client.post(
        f"/api/v1/repositories/{git_repo.id}/agent/tasks/{approved_task.id}/pull-request",
        headers=headers_b
    )
    assert resp.status_code == 404
