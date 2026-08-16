import pytest
import os
import zipfile
import shutil
import io
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.github import GitHubInstallation
from app.models.repository import Repository
from app.services.repository import (
    RepositoryService,
    get_safe_workspace_path,
    should_exclude_file,
    is_binary_file
)

@pytest.fixture
def auth_user(db_session: Session) -> User:
    user = db_session.query(User).filter(User.email == "developer@codeforge.ai").first()
    if not user:
        user = User(
            email="developer@codeforge.ai",
            hashed_password="hashed_password_mock_12345",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture
def other_user(db_session: Session) -> User:
    user = db_session.query(User).filter(User.email == "other@codeforge.ai").first()
    if not user:
        user = User(
            email="other@codeforge.ai",
            hashed_password="hashed_password_mock_54321",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture
def auth_headers(auth_user: User) -> dict:
    from tests.test_auth import create_test_token
    token = create_test_token(user_id=str(auth_user.id))
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def other_headers(other_user: User) -> dict:
    from tests.test_auth import create_test_token
    token = create_test_token(user_id=str(other_user.id))
    return {"Authorization": f"Bearer {token}"}

# --- 1. Security Path Traversal Validation Tests ---

def test_get_safe_workspace_path_valid():
    base_dir = os.path.realpath("C:/workspaces/user_1/repo_123")
    
    # Empty relative resolves to base
    assert get_safe_workspace_path(base_dir, "") == base_dir
    assert get_safe_workspace_path(base_dir, "src/main.py") == os.path.join(base_dir, "src", "main.py")

def test_get_safe_workspace_path_absolute_path_rejection():
    base_dir = os.path.realpath("C:/workspaces/user_1/repo_123")
    
    # Unix absolute paths
    with pytest.raises(PermissionError, match="Absolute paths are forbidden|Absolute, UNC, or drive"):
        get_safe_workspace_path(base_dir, "/etc/passwd")
        
    # Windows absolute paths
    with pytest.raises(PermissionError, match="Absolute paths are forbidden|Absolute, UNC, or drive"):
        get_safe_workspace_path(base_dir, "C:\\Windows\\System32")
        
    # UNC absolute paths
    with pytest.raises(PermissionError, match="Absolute paths are forbidden|Absolute, UNC, or drive"):
        get_safe_workspace_path(base_dir, "\\\\server\\share\\file.txt")

    # Drive prefix relative paths
    with pytest.raises(PermissionError, match="Absolute paths are forbidden|Absolute, UNC, or drive"):
        get_safe_workspace_path(base_dir, "D:relative/path")

def test_get_safe_workspace_path_directory_traversal_rejection():
    base_dir = os.path.realpath("C:/workspaces/user_1/repo_123")
    
    # Traversal segments
    with pytest.raises(PermissionError, match="Directory traversal components are forbidden"):
        get_safe_workspace_path(base_dir, "../../etc/passwd")
        
    with pytest.raises(PermissionError, match="Directory traversal components are forbidden"):
        get_safe_workspace_path(base_dir, "src/../../etc/passwd")

def test_get_safe_workspace_path_sibling_prefix_rejection():
    # Tests that commonpath boundary check prevents sibling workspace directory access
    base_dir = os.path.realpath("C:/workspaces/user_1/repo_123")
    target_rel = "../repo_123_evil/sensitive.txt"
    
    with pytest.raises(PermissionError):
        get_safe_workspace_path(base_dir, target_rel)

# --- 2. Exclude Filters & Binary Tests ---

def test_should_exclude_file_rules():
    assert should_exclude_file(".env") is True
    assert should_exclude_file(".env.local") is True
    assert should_exclude_file("id_rsa") is True
    assert should_exclude_file("key.pem") is True
    assert should_exclude_file("main.pem") is True
    assert should_exclude_file("image.png") is True
    assert should_exclude_file("archive.zip") is True
    
    # Allowed files
    assert should_exclude_file("main.py") is False
    assert should_exclude_file("package.json") is False
    assert should_exclude_file("README.md") is False

def test_is_binary_file_detection(tmp_path):
    # Text file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("hello standard text content")
    assert is_binary_file(str(txt_file)) is False
    
    # Binary file (contains null byte)
    bin_file = tmp_path / "test.bin"
    bin_file.write_bytes(b"hello\x00binary\x00content")
    assert is_binary_file(str(bin_file)) is True

# --- 3. Secure ZIP Extraction Tests ---

def test_extract_zip_securely_limits(tmp_path):
    # Zip bomb - too many files
    mem_zip_count = io.BytesIO()
    with zipfile.ZipFile(mem_zip_count, "w") as z:
        for i in range(1005):
            z.writestr(f"file_{i}.txt", "content")
            
    with pytest.raises(ValueError, match="ZIP archive contains too many files"):
        RepositoryService.extract_zip_securely(mem_zip_count.getvalue(), str(tmp_path))
        
    # Zip bomb - size exceeds 50MB
    mem_zip_size = io.BytesIO()
    with zipfile.ZipFile(mem_zip_size, "w") as z:
        # Create a compressed file that expands to large size
        z.writestr("large.txt", "x" * (51 * 1024 * 1024))
        
    with pytest.raises(ValueError, match="ZIP archive extracted size exceeds limit"):
        RepositoryService.extract_zip_securely(mem_zip_size.getvalue(), str(tmp_path))

def test_extract_zip_securely_traversal_filtering(tmp_path):
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w") as z:
        z.writestr("safe_file.py", "print('hello')")
        # Traversal name in zip headers
        z.writestr("../traversal_file.txt", "hacked")
        # Absolute name
        z.writestr("/etc/passwd", "hacked")
        # Excluded folder segment
        z.writestr(".git/config", "hacked")
        z.writestr("node_modules/express/index.js", "hacked")
        
    target_dir = tmp_path / "workspace"
    RepositoryService.extract_zip_securely(mem_zip.getvalue(), str(target_dir))
    
    # Safe file should be extracted
    assert (target_dir / "safe_file.py").exists()
    
    # Traversal/Absolute/Excluded should NOT exist
    assert not (target_dir / "traversal_file.txt").exists()
    assert not (target_dir / "etc").exists()
    assert not (target_dir / ".git").exists()
    assert not (target_dir / "node_modules").exists()

# --- 4. Workspace Indexing Tests ---

def test_index_codebase_ratios(tmp_path):
    # Setup test workspace
    workspace = tmp_path / "repo"
    workspace.mkdir()
    
    # Add files
    (workspace / "main.py").write_text("import os")
    (workspace / "utils.py").write_text("def helper(): pass")
    (workspace / "index.ts").write_text("const x = 1;")
    (workspace / "package.json").write_text('{"dependencies": {"react": "18.0"}}')
    (workspace / "requirements.txt").write_text("fastapi>=0.100")
    
    # Add excluded structures (should be pruned)
    node_dir = workspace / "node_modules"
    node_dir.mkdir()
    (node_dir / "index.js").write_text("leak")
    
    data = RepositoryService.index_codebase(str(workspace))
    
    assert "Python" in data["languages"]
    assert "TypeScript" in data["languages"]
    # 2 Python files, 1 TypeScript file, 1 JSON file (total 4)
    assert data["languages"]["Python"] == 50.0
    assert data["languages"]["TypeScript"] == 25.0
    
    assert "React" in data["frameworks"]
    assert "FastAPI" in data["frameworks"]
    
    assert "package.json" in data["dependency_files"]
    assert "requirements.txt" in data["dependency_files"]
    
    # Pruning validation
    assert data["file_count"] == 5  # main, utils, ts, package, requirements (ignores node_modules)

# --- 5. API Route Integration Tests ---

def test_api_unauthorized_access(client: TestClient):
    # GET /repositories lists should return 401 Unauthorized without token
    response = client.get("/api/v1/repositories")
    assert response.status_code == 401

def test_api_import_flow(
    client: TestClient, 
    db_session: Session, 
    auth_user: User, 
    auth_headers: dict
):
    with patch.object(Session, "commit", new=db_session.flush):
        # Add GitHub App installation record
        installation = GitHubInstallation(
            user_id=auth_user.id,
            installation_id=98765,
            github_account_id=12345,
            github_account_login="codeforge-dev",
            github_account_type="User"
        )
        db_session.add(installation)
        db_session.commit()
        # Create a valid minimal zipball bytes payload
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, "w") as z:
            z.writestr("owner-repo-commit/README.md", "# Target Repo")
            z.writestr("owner-repo-commit/main.py", "import os")
        valid_zip_bytes = mem_zip.getvalue()

        # Mock Background task and GitHubService API requests
        with patch("app.services.github.GitHubService.get_repository") as mock_get_repo, \
             patch("app.services.github.GitHubService.download_repository_zipball") as mock_download_zip, \
             patch("app.services.repository.RepositoryService.index_codebase") as mock_index:
             
             mock_get_repo.return_value = {
                 "name": "target-repo",
                 "full_name": "codeforge-dev/target-repo",
                 "owner": {"login": "codeforge-dev"},
                 "default_branch": "main"
             }
             mock_download_zip.return_value = valid_zip_bytes
             mock_index.return_value = {
                 "languages": {"Python": 100.0},
                 "frameworks": ["FastAPI"],
                 "dependency_files": ["requirements.txt"],
                 "file_count": 1
             }
             
             # Trigger import
             response = client.post(
                 "/api/v1/repositories/import",
                 headers=auth_headers,
                 json={"github_repo_id": 999111}
             )
             assert response.status_code == 202
             data = response.json()
             assert data["github_repo_id"] == 999111
             
             # Duplicate check
             response_dup = client.post(
                 "/api/v1/repositories/import",
                 headers=auth_headers,
                 json={"github_repo_id": 999111}
             )
             assert response_dup.status_code == 202
             
             # Fetch from database to check index status (background task runs synchronously during request in TestClient)
             repo = db_session.query(Repository).filter(Repository.github_repo_id == 999111).first()
             assert repo is not None
             assert repo.status == "indexed"
             assert repo.languages == {"Python": 100.0}
             assert repo.frameworks == ["FastAPI"]

def test_api_ownership_enforcement(
    client: TestClient, 
    db_session: Session, 
    auth_user: User, 
    other_user: User, 
    auth_headers: dict,
    other_headers: dict
):
    # Import repo owned by auth_user
    repo = Repository(
        user_id=auth_user.id,
        github_repo_id=222333,
        name="auth-repo",
        full_name="dev/auth-repo",
        owner="dev",
        default_branch="main",
        local_path="C:/dummy/path",
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    # Authenticated user should see it
    response = client.get(f"/api/v1/repositories/{repo.id}", headers=auth_headers)
    assert response.status_code == 200
    
    # Other user should get 404 Not Found
    response_other = client.get(f"/api/v1/repositories/{repo.id}", headers=other_headers)
    assert response_other.status_code == 404

def test_api_secure_file_reading(
    client: TestClient, 
    db_session: Session, 
    auth_user: User, 
    auth_headers: dict,
    tmp_path
):
    # Setup safe workspace folder on disk
    workspace = tmp_path / "user_workspace"
    workspace.mkdir()
    
    safe_file = workspace / "code.py"
    safe_file.write_text("print('safe text content')")
    
    sensitive_file = workspace / ".env"
    sensitive_file.write_text("DATABASE_URL=hacked")
    
    large_file = workspace / "large.py"
    large_file.write_text("x" * (1024 * 1024 + 10))  # Exceeds 1MB
    
    # Create DB entry pointing to this workspace
    repo = Repository(
        user_id=auth_user.id,
        github_repo_id=444555,
        name="workspace-repo",
        full_name="dev/workspace-repo",
        owner="dev",
        default_branch="main",
        local_path=str(workspace),
        status="indexed"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    # 1. Read safe file
    response = client.get(
        f"/api/v1/repositories/{repo.id}/file?path=code.py",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["content"] == "print('safe text content')"
    
    # 2. Read sensitive file (should be blocked with 403)
    response_sec = client.get(
        f"/api/v1/repositories/{repo.id}/file?path=.env",
        headers=auth_headers
    )
    assert response_sec.status_code == 403
    
    # 3. Read too large file (should be blocked with 400)
    response_large = client.get(
        f"/api/v1/repositories/{repo.id}/file?path=large.py",
        headers=auth_headers
    )
    assert response_large.status_code == 400

    # 4. Traversal read path (should be blocked with 403 PermissionError)
    response_traverse = client.get(
        f"/api/v1/repositories/{repo.id}/file?path=../outside.txt",
        headers=auth_headers
    )
    assert response_traverse.status_code == 403

def test_api_repository_deletion(
    client: TestClient, 
    db_session: Session, 
    auth_user: User, 
    auth_headers: dict,
    tmp_path
):
    # Setup folder inside settings.workspace_root_resolved boundary to test deletes
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    
    # Mock settings.workspace_root_resolved using direct configuration set
    old_root = settings.WORKSPACE_ROOT
    settings.WORKSPACE_ROOT = str(workspace_root)
    
    try:
        user_root = workspace_root / f"user_{auth_user.id}"
        user_root.mkdir()
        
        repo_workspace = user_root / "repo_777888"
        repo_workspace.mkdir()
        (repo_workspace / "code.py").write_text("data")
        
        # Create DB repository
        repo = Repository(
            user_id=auth_user.id,
            github_repo_id=777888,
            name="del-repo",
            full_name="dev/del-repo",
            owner="dev",
            default_branch="main",
            local_path=str(repo_workspace),
            status="indexed"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)
        
        # Verify workspace directory exists before API call
        assert repo_workspace.exists()
        
        # Delete repo
        response = client.delete(f"/api/v1/repositories/{repo.id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Verify directory is deleted recursively
        assert not repo_workspace.exists()
        
        # Verify record is deleted from DB
        db_repo = db_session.query(Repository).filter(Repository.id == repo.id).first()
        assert db_repo is None
    finally:
        settings.WORKSPACE_ROOT = old_root
