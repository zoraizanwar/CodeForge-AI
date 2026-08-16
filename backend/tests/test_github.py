import pytest
import jwt
import secrets
import hashlib
import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.config import settings
from app.models.user import User
from app.models.github import GitHubInstallation, OAuthState
from app.services.github import GitHubService

# Generate a session-scoped RSA private key to sign test JWTs with RS256
@pytest.fixture(scope="session")
def test_private_key_pem() -> str:
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")

@pytest.fixture
def mock_github_config(test_private_key_pem, tmp_path):
    # Write the private key to a temporary file
    pem_file = tmp_path / "test-key.pem"
    pem_file.write_text(test_private_key_pem)
    
    with patch.object(settings, "GITHUB_APP_ID", 12345), \
         patch.object(settings, "GITHUB_CLIENT_ID", "mock_client_id"), \
         patch.object(settings, "GITHUB_CLIENT_SECRET", "mock_client_secret"), \
         patch.object(settings, "GITHUB_PRIVATE_KEY_PATH", str(pem_file)):
        yield pem_file

@pytest.fixture
def auth_user(db_session: Session) -> User:
    # Check if user already exists
    user = db_session.query(User).filter(User.email == "dev@codeforge.ai").first()
    if not user:
        user = User(
            email="dev@codeforge.ai",
            hashed_password="hashed_password_mock_12345",
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

# 1. Config Validation Tests
def test_github_service_missing_config():
    with patch.object(settings, "GITHUB_APP_ID", None):
        with pytest.raises(ValueError) as exc_info:
            GitHubService()
        assert "Required GitHub App configurations" in str(exc_info.value)

# 2. JWT Generation Tests
def test_github_jwt_generation(mock_github_config, test_private_key_pem):
    service = GitHubService()
    token = service.generate_app_jwt()
    
    # Decode and verify payload claims without signature checking (just parsing)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["iss"] == "12345"
    assert "iat" in payload
    assert "exp" in payload
    # Expiration should be set to 10 minutes total duration from iat (now - 60s) to exp (now + 540s)
    assert payload["exp"] - payload["iat"] == 600

# 3. OAuth State Generation
def test_oauth_state_generation(client: TestClient, db_session: Session, auth_user: User, auth_headers: dict):
    response = client.get("/api/v1/github/connect", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "state=" in data["url"]
    
    # Extract state parameter
    state_token = data["url"].split("state=")[1]
    state_hash = hashlib.sha256(state_token.encode("utf-8")).hexdigest()
    
    # Check database record
    db_state = db_session.query(OAuthState).filter(OAuthState.state_hash == state_hash).first()
    assert db_state is not None
    assert db_state.user_id == auth_user.id
    assert db_state.used_at is None
    assert db_state.expires_at > datetime.datetime.now(datetime.timezone.utc)

# 4. Callback Handling & State Validation
@pytest.mark.asyncio
async def test_github_callback_success(
    client: TestClient, 
    db_session: Session, 
    auth_user: User, 
    mock_github_config
):
    # Insert state directly in DB
    state_token = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state_token.encode("utf-8")).hexdigest()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    
    db_state = OAuthState(
        user_id=auth_user.id,
        state_hash=state_hash,
        expires_at=expires_at
    )
    db_session.add(db_state)
    db_session.commit()
    
    mock_details = {
        "id": 9988,
        "account": {
            "id": 887766,
            "login": "codeforge-dev",
            "type": "User"
        }
    }
    
    with patch("app.services.github.GitHubService.get_installation_details") as mock_details_call:
        mock_details_call.return_value = mock_details
        
        response = client.get(
            f"/api/v1/github/callback?state={state_token}&installation_id=9988",
            follow_redirects=False
        )
        
        # Verify redirect
        assert response.status_code == 307
        assert "/?github=connected" in response.headers["location"]

        
        # Verify state is marked as used
        db_session.refresh(db_state)
        assert db_state.used_at is not None
        
        # Verify installation links correctly
        db_install = db_session.query(GitHubInstallation).filter(
            GitHubInstallation.user_id == auth_user.id
        ).first()
        assert db_install is not None
        assert db_install.installation_id == 9988
        assert db_install.github_account_login == "codeforge-dev"
        assert db_install.github_account_type == "User"

# 5. OAuth State Expiration Checks
def test_github_callback_expired_state(client: TestClient, db_session: Session, auth_user: User, mock_github_config):
    state_token = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state_token.encode("utf-8")).hexdigest()
    # Expired 5 minutes ago
    expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    
    db_state = OAuthState(
        user_id=auth_user.id,
        state_hash=state_hash,
        expires_at=expires_at
    )
    db_session.add(db_state)
    db_session.commit()
    
    response = client.get(f"/api/v1/github/callback?state={state_token}&installation_id=9988")
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]

# 6. OAuth State Reuse Prevention
def test_github_callback_reused_state(client: TestClient, db_session: Session, auth_user: User, mock_github_config):
    state_token = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state_token.encode("utf-8")).hexdigest()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    
    db_state = OAuthState(
        user_id=auth_user.id,
        state_hash=state_hash,
        expires_at=expires_at,
        used_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add(db_state)
    db_session.commit()
    
    response = client.get(f"/api/v1/github/callback?state={state_token}&installation_id=9988")
    assert response.status_code == 400
    assert "already been used" in response.json()["detail"]

# 7. OAuth Status Checking
def test_github_status_disconnected(client: TestClient, auth_headers: dict):
    response = client.get("/api/v1/github/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"connected": False}

def test_github_status_connected(client: TestClient, db_session: Session, auth_user: User, auth_headers: dict):
    installation = GitHubInstallation(
        user_id=auth_user.id,
        installation_id=123,
        github_account_id=999,
        github_account_login="github_test_user",
        github_account_type="User"
    )
    db_session.add(installation)
    db_session.commit()
    
    response = client.get("/api/v1/github/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["github_login"] == "github_test_user"
    assert data["github_account_type"] == "User"

# 8. Repository Listings
def test_github_repositories(client: TestClient, db_session: Session, auth_user: User, auth_headers: dict, mock_github_config):
    installation = GitHubInstallation(
        user_id=auth_user.id,
        installation_id=123,
        github_account_id=999,
        github_account_login="github_test_user",
        github_account_type="User"
    )
    db_session.add(installation)
    db_session.commit()
    
    mock_repos = {
        "total_count": 1,
        "repositories": [
            {
                "id": 1234,
                "name": "codeforge-ai",
                "full_name": "github_test_user/codeforge-ai",
                "private": True,
                "html_url": "https://github.com/github_test_user/codeforge-ai",
                "default_branch": "main",
                "owner": {
                    "id": 999,
                    "login": "github_test_user",
                    "type": "User"
                }
            }
        ]
    }
    
    with patch("app.services.github.GitHubService.list_repositories") as mock_list_repos:
        mock_list_repos.return_value = mock_repos
        
        response = client.get("/api/v1/github/repositories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["repositories"]) == 1
        
        repo = data["repositories"][0]
        assert repo["name"] == "codeforge-ai"
        assert repo["private"] is True
        # Verify no access tokens are exposed in API response
        assert "token" not in response.text
        assert "secret" not in response.text

# 9. API Failure Handling
def test_github_repositories_api_failure(client: TestClient, db_session: Session, auth_user: User, auth_headers: dict, mock_github_config):
    installation = GitHubInstallation(
        user_id=auth_user.id,
        installation_id=123,
        github_account_id=999,
        github_account_login="github_test_user",
        github_account_type="User"
    )
    db_session.add(installation)
    db_session.commit()
    
    with patch("app.services.github.GitHubService.list_repositories") as mock_list_repos:
        mock_list_repos.side_effect = RuntimeError("GitHub API connection error")
        
        response = client.get("/api/v1/github/repositories", headers=auth_headers)
        assert response.status_code == 502
        assert "GitHub API integration error" in response.json()["detail"]

# 10. Disconnect behavior
def test_github_disconnect(client: TestClient, db_session: Session, auth_user: User, auth_headers: dict):
    installation = GitHubInstallation(
        user_id=auth_user.id,
        installation_id=123,
        github_account_id=999,
        github_account_login="github_test_user",
        github_account_type="User"
    )
    db_session.add(installation)
    db_session.commit()
    
    response = client.delete("/api/v1/github/disconnect", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Check db is empty
    assert db_session.query(GitHubInstallation).filter(GitHubInstallation.user_id == auth_user.id).first() is None

# 11. Endpoint protections (Unauthenticated Reject)
def test_unauthenticated_endpoint_rejection(client: TestClient):
    endpoints = [
        ("/api/v1/github/connect", "GET"),
        ("/api/v1/github/status", "GET"),
        ("/api/v1/github/repositories", "GET"),
        ("/api/v1/github/disconnect", "DELETE")
    ]
    for path, method in endpoints:
        if method == "GET":
            response = client.get(path)
        else:
            response = client.delete(path)
        assert response.status_code == 401

# 12. User Isolation & Installation Uniqueness
def test_user_isolation_on_repositories(client: TestClient, db_session: Session, auth_headers: dict):
    # Create another user and associate the installation to them
    other_user = User(
        email="other@codeforge.ai",
        hashed_password="other_hashed_password",
        is_active=True
    )
    db_session.add(other_user)
    db_session.commit()
    
    installation = GitHubInstallation(
        user_id=other_user.id,
        installation_id=123,
        github_account_id=999,
        github_account_login="github_test_user",
        github_account_type="User"
    )
    db_session.add(installation)
    db_session.commit()
    
    # Requesting as auth_user should return 404 since auth_user has no connected installation
    response = client.get("/api/v1/github/repositories", headers=auth_headers)
    assert response.status_code == 404

def test_installation_uniqueness_linking_conflict(
    client: TestClient, 
    db_session: Session, 
    auth_user: User, 
    mock_github_config
):
    # Other user has installation ID 123
    other_user = User(email="other@codeforge.ai", hashed_password="pw", is_active=True)
    db_session.add(other_user)
    db_session.commit()
    
    installation = GitHubInstallation(
        user_id=other_user.id,
        installation_id=123,
        github_account_id=999,
        github_account_login="github_test_user",
        github_account_type="User"
    )
    db_session.add(installation)
    
    # Generate callback state for auth_user
    state_token = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state_token.encode("utf-8")).hexdigest()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    db_state = OAuthState(user_id=auth_user.id, state_hash=state_hash, expires_at=expires_at)
    db_session.add(db_state)
    db_session.commit()
    
    mock_details = {
        "id": 123,
        "account": {"id": 999, "login": "github_test_user", "type": "User"}
    }
    
    with patch("app.services.github.GitHubService.get_installation_details") as mock_details_call:
        mock_details_call.return_value = mock_details
        
        # auth_user tries to associate installation ID 123 to themselves
        response = client.get(f"/api/v1/github/callback?state={state_token}&installation_id=123")
        assert response.status_code == 409
        assert "linked to another CodeForge account" in response.json()["detail"]
