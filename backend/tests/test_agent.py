"""
Step 7 Tests: AI Software Engineer Agent - Planning & Code Generation.

Tests coverage:
  - Task creation & validation
  - JWT Authentication & repository ownership
  - Task listing & status detail
  - Plan & changes endpoints
  - Tenant isolation & permission boundaries
  - Context retrieval service
  - Implementation planner service
  - Code generator & unified diff generation
  - Security validation: absolute path, traversal, sensitive file, excluded directory, max files, max size limits
  - Full background orchestrator workflow execution
"""
import uuid
import pytest
import bcrypt
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.user import User
from app.models.agent import AgentTask
from app.models.knowledge import RepositoryAnalysis, SourceFile, Symbol
from app.schemas.agent import (
    TaskCreateRequest,
    ImplementationPlanSchema,
    CodeGenerationResponseSchema,
    FileChangeSchema
)
from app.services.agent.validator import (
    validate_proposed_change,
    validate_proposed_changes,
    ChangeValidationError,
    MAX_CHANGED_FILES,
    MAX_FILE_SIZE_BYTES
)
from app.services.agent.diff_generator import generate_unified_diff
from app.services.agent.context_retriever import retrieve_task_context
from app.services.agent.planner import generate_implementation_plan
from app.services.agent.code_generator import generate_code_changes
from app.services.agent.orchestrator import run_agent_task_pipeline
from app.providers.ai.grok import GrokProvider
from tests.test_auth import create_test_token


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def agent_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="agent_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def other_agent_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="other_agent_user@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def auth_headers(agent_user: User) -> dict:
    token = create_test_token(user_id=str(agent_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_auth_headers(other_agent_user: User) -> dict:
    token = create_test_token(user_id=str(other_agent_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agent_repo(db_session: Session, agent_user: User, tmp_path) -> Repository:
    """Creates a test repository with workspace folder."""
    repo_dir = tmp_path / "test_agent_repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("def main():\n    print('Hello World')\n", encoding="utf-8")
    (repo_dir / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")

    repo = Repository(
        user_id=agent_user.id,
        github_repo_id=778899,
        name="test-agent-repo",
        full_name="testuser/test-agent-repo",
        owner="testuser",
        default_branch="main",
        local_path=str(repo_dir),
        status="indexed",
        frameworks=["FastAPI"],
        dependency_files={"requirements.txt": "fastapi==0.100.0"}
    )
    db_session.add(repo)
    db_session.flush()

    # Add analysis metadata
    analysis = RepositoryAnalysis(
        repository_id=repo.id,
        status="completed",
        architecture_summary="FastAPI backend application",
        entry_points=["main.py"],
        dependencies_parsed={"fastapi": "0.100.0"}
    )
    db_session.add(analysis)

    # Add SourceFile and Symbol
    sf = SourceFile(
        repository_id=repo.id,
        path="main.py",
        language="Python",
        size_bytes=45,
        hash="abcdef1234567890"
    )
    db_session.add(sf)
    db_session.flush()

    sym = Symbol(
        source_file_id=sf.id,
        name="main",
        type="function",
        line_number=1,
        end_line_number=2
    )
    db_session.add(sym)
    db_session.commit()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def agent_task(db_session: Session, agent_user: User, agent_repo: Repository) -> AgentTask:
    """Creates a sample agent task."""
    task = AgentTask(
        user_id=agent_user.id,
        repository_id=agent_repo.id,
        task_description="Add a new health check endpoint to main.py",
        status="ready_for_review",
        plan={
            "task_summary": "Add health check endpoint",
            "architecture_understanding": "FastAPI app",
            "relevant_files": ["main.py"],
            "relevant_symbols": ["main"],
            "proposed_changes": ["Add /health route"],
            "dependencies_affected": [],
            "tests": ["test_health"],
            "implementation_order": ["1. Update main.py"],
            "risks": []
        },
        files_analyzed=["main.py"],
        files_to_modify=["main.py"],
        changes=[{
            "file_path": "main.py",
            "operation": "modify",
            "original_content": "def main():\n    print('Hello World')\n",
            "proposed_content": "def main():\n    print('Hello World')\n\ndef health():\n    return {'status': 'ok'}\n",
            "explanation": "Add health check endpoint",
            "confidence": 0.95,
            "diff": "--- a/main.py\n+++ b/main.py\n@@ -1,2 +1,5 @@\n def main():\n     print('Hello World')\n+\n+def health():\n+    return {'status': 'ok'}\n"
        }]
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


# ═══════════════════════════════════════════════════════════════════════════
# 1. API Endpoints & Auth Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_create_agent_task_requires_auth(client: TestClient, agent_repo: Repository):
    """POST task without auth header returns 401."""
    res = client.post(f"/api/v1/repositories/{agent_repo.id}/agent/tasks", json={"task": "Refactor router"})
    assert res.status_code == 401


def test_create_agent_task_validates_blank_task(client: TestClient, auth_headers: dict, agent_repo: Repository):
    """POST task with empty string returns 422."""
    res = client.post(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks",
        headers=auth_headers,
        json={"task": "   "}
    )
    assert res.status_code == 422


def test_create_agent_task_verifies_repo_ownership(client: TestClient, second_auth_headers: dict, agent_repo: Repository):
    """User B cannot create a task on User A's repo."""
    res = client.post(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks",
        headers=second_auth_headers,
        json={"task": "Add new user model"}
    )
    assert res.status_code == 404


def test_create_agent_task_returns_202(client: TestClient, auth_headers: dict, agent_repo: Repository):
    """Creating an agent task returns 202 Accepted and creates task in DB."""
    res = client.post(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks",
        headers=auth_headers,
        json={"task": "Add logging to helper functions"}
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] in ("pending", "analyzing")
    assert data["task_description"] == "Add logging to helper functions"
    assert "id" in data


def test_list_agent_tasks(client: TestClient, auth_headers: dict, agent_repo: Repository, agent_task: AgentTask):
    """GET tasks returns list of tasks for the specified repository."""
    res = client.get(f"/api/v1/repositories/{agent_repo.id}/agent/tasks", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert any(t["id"] == str(agent_task.id) for t in data)


def test_get_agent_task_detail(client: TestClient, auth_headers: dict, agent_repo: Repository, agent_task: AgentTask):
    """GET task detail returns full task information."""
    res = client.get(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks/{agent_task.id}",
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(agent_task.id)
    assert data["status"] == "ready_for_review"


def test_get_agent_task_plan(client: TestClient, auth_headers: dict, agent_repo: Repository, agent_task: AgentTask):
    """GET task plan returns structured implementation plan."""
    res = client.get(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks/{agent_task.id}/plan",
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_summary"] == "Add health check endpoint"
    assert "main.py" in data["relevant_files"]


def test_get_agent_task_changes(client: TestClient, auth_headers: dict, agent_repo: Repository, agent_task: AgentTask):
    """GET task changes returns generated code changes and diffs."""
    res = client.get(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks/{agent_task.id}/changes",
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_id"] == str(agent_task.id)
    assert len(data["changes"]) == 1
    assert data["changes"][0]["file_path"] == "main.py"
    assert "diff" in data["changes"][0]


def test_tenant_isolation_tasks(client: TestClient, second_auth_headers: dict, agent_repo: Repository, agent_task: AgentTask):
    """User B cannot fetch User A's task, plan, or changes."""
    res_task = client.get(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks/{agent_task.id}",
        headers=second_auth_headers
    )
    assert res_task.status_code == 404

    res_plan = client.get(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks/{agent_task.id}/plan",
        headers=second_auth_headers
    )
    assert res_plan.status_code == 404

    res_changes = client.get(
        f"/api/v1/repositories/{agent_repo.id}/agent/tasks/{agent_task.id}/changes",
        headers=second_auth_headers
    )
    assert res_changes.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 2. Security & Validation Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_validation_absolute_path_rejection(agent_repo: Repository):
    """Absolute paths are rejected by validation."""
    with pytest.raises(ChangeValidationError) as excinfo:
        validate_proposed_change(agent_repo.local_path, "/etc/passwd", "modify", "data")
    assert "Absolute" in str(excinfo.value) or "forbidden" in str(excinfo.value)

    with pytest.raises(ChangeValidationError):
        validate_proposed_change(agent_repo.local_path, "C:\\Windows\\System32\\cmd.exe", "create", "data")


def test_validation_traversal_rejection(agent_repo: Repository):
    """Path traversal sequences (..) are rejected."""
    with pytest.raises(ChangeValidationError) as excinfo:
        validate_proposed_change(agent_repo.local_path, "../outside.py", "create", "data")
    assert "traversal" in str(excinfo.value).lower() or "outside" in str(excinfo.value).lower()


def test_validation_sensitive_file_rejection(agent_repo: Repository):
    """Targeting sensitive files (.env, .pem, key) raises ChangeValidationError."""
    with pytest.raises(ChangeValidationError) as excinfo:
        validate_proposed_change(agent_repo.local_path, ".env", "modify", "SECRET=123")
    assert "sensitive" in str(excinfo.value).lower() or "protected" in str(excinfo.value).lower()

    with pytest.raises(ChangeValidationError):
        validate_proposed_change(agent_repo.local_path, "certs/server.pem", "create", "cert data")


def test_validation_excluded_directory_rejection(agent_repo: Repository):
    """Targeting files inside excluded directories (.git, node_modules) raises error."""
    with pytest.raises(ChangeValidationError) as excinfo:
        validate_proposed_change(agent_repo.local_path, ".git/config", "modify", "data")
    assert "excluded directory" in str(excinfo.value).lower()

    with pytest.raises(ChangeValidationError):
        validate_proposed_change(agent_repo.local_path, "node_modules/express/index.js", "modify", "data")


def test_validation_max_changed_files_limit(agent_repo: Repository):
    """Exceeding MAX_CHANGED_FILES limit raises error."""
    changes = [
        {"file_path": f"file_{i}.py", "operation": "create", "proposed_content": "pass"}
        for i in range(MAX_CHANGED_FILES + 1)
    ]
    with pytest.raises(ChangeValidationError) as excinfo:
        validate_proposed_changes(agent_repo.local_path, changes)
    assert "exceeds maximum allowed" in str(excinfo.value)


def test_validation_max_file_size_limit(agent_repo: Repository):
    """Exceeding 500KB file content raises error."""
    large_content = "x" * (MAX_FILE_SIZE_BYTES + 10)
    with pytest.raises(ChangeValidationError) as excinfo:
        validate_proposed_change(agent_repo.local_path, "large.py", "create", large_content)
    assert "exceeds maximum size limit" in str(excinfo.value)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Agent Core Services Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_diff_generator_create():
    """Diff generator for create operation."""
    diff = generate_unified_diff("new_file.py", "", "print('hello')\n", "create")
    assert "+++ b/new_file.py" in diff
    assert "+print('hello')" in diff


def test_diff_generator_modify():
    """Diff generator for modify operation."""
    orig = "def foo():\n    return 1\n"
    prop = "def foo():\n    return 2\n"
    diff = generate_unified_diff("foo.py", orig, prop, "modify")
    assert "-    return 1" in diff
    assert "+    return 2" in diff


def test_context_retrieval(db_session: Session, agent_repo: Repository):
    """retrieve_task_context extracts overview, symbols, and files."""
    ctx = retrieve_task_context(db_session, agent_repo, "add health check to main.py")
    assert ctx.repository_name == "testuser/test-agent-repo"
    assert "main.py" in ctx.files_analyzed
    assert len(ctx.relevant_symbols) >= 1
    assert "main" in [s["name"] for s in ctx.relevant_symbols]
    assert ctx.token_count > 0


@pytest.mark.asyncio
async def test_planner_service(db_session: Session, agent_repo: Repository):
    """generate_implementation_plan returns structured plan."""
    ctx = retrieve_task_context(db_session, agent_repo, "refactor main.py")
    provider = GrokProvider()  # Uses mock mode
    plan = await generate_implementation_plan(provider, "refactor main.py", ctx)

    assert isinstance(plan, ImplementationPlanSchema)
    assert plan.task_summary != ""
    assert len(plan.relevant_files) >= 1


@pytest.mark.asyncio
async def test_code_generator_service(db_session: Session, agent_repo: Repository):
    """generate_code_changes returns validated changes with diffs."""
    ctx = retrieve_task_context(db_session, agent_repo, "add print statement to main.py")
    provider = GrokProvider()
    plan = await generate_implementation_plan(provider, "add print statement", ctx)

    res = await generate_code_changes(
        ai_provider=provider,
        repo_local_path=agent_repo.local_path,
        task_description="add print statement",
        plan=plan,
        context=ctx
    )

    assert isinstance(res, CodeGenerationResponseSchema)
    assert len(res.changes) >= 1
    assert res.changes[0].diff != ""


# ═══════════════════════════════════════════════════════════════════════════
# 4. Orchestrator Workflow Pipeline Test
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_orchestrator_pipeline(db_session: Session, agent_user: User, agent_repo: Repository):
    """Full execution of run_agent_task_pipeline transitions status from pending to ready_for_review."""
    task = AgentTask(
        user_id=agent_user.id,
        repository_id=agent_repo.id,
        task_description="Implement new helper function in main.py",
        status="pending"
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    # Execute orchestrator pipeline synchronously with test db_session
    await run_agent_task_pipeline(task.id, db=db_session)

    # Refresh task state from DB
    db_session.refresh(task)
    assert task.status == "ready_for_review"
    assert task.plan is not None
    assert "task_summary" in task.plan
    assert task.files_analyzed is not None
    assert "main.py" in task.files_analyzed
    assert task.files_to_modify is not None
    assert task.changes is not None
    assert len(task.changes) >= 1
    assert task.completed_at is not None
