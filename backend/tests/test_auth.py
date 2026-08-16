import pytest
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.user import User
from app.core.security import verify_password

# Helper to create custom tokens for test verification
def create_test_token(
    user_id: str, 
    secret: str = None, 
    algorithm: str = None, 
    expire_minutes: int = 30,
    include_sub: bool = True
) -> str:
    secret = secret or settings.JWT_SECRET_KEY
    algorithm = algorithm or settings.JWT_ALGORITHM
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    
    payload = {}
    if include_sub:
        payload["sub"] = user_id
    payload["iat"] = now
    payload["exp"] = expire
    
    return jwt.encode(payload, secret, algorithm=algorithm)

def test_register_success(client: TestClient, db_session: Session):
    """Validates successful user registration and security checks."""
    payload = {"email": "test@codeforge.ai", "password": "secure-password-123"}
    response = client.post("/api/v1/auth/register", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "test@codeforge.ai"
    assert data["is_active"] is True
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify database state
    user = db_session.query(User).filter(User.email == "test@codeforge.ai").first()
    assert user is not None
    assert user.hashed_password != "secure-password-123"
    assert verify_password("secure-password-123", user.hashed_password) is True

def test_register_invalid_email(client: TestClient):
    """Validates that registrations with invalid email formats are rejected."""
    payloads = [
        {"email": "notanemail", "password": "secure-password-123"},
        {"email": "user@example", "password": "secure-password-123"},
        {"email": "   ", "password": "secure-password-123"},
    ]
    for p in payloads:
        response = client.post("/api/v1/auth/register", json=p)
        assert response.status_code == 422

def test_register_weak_password(client: TestClient):
    """Validates that weak passwords (fewer than 8 characters) are rejected."""
    payloads = [
        {"email": "user@codeforge.ai", "password": "123"},
        {"email": "user@codeforge.ai", "password": "       "},
        {"email": "user@codeforge.ai", "password": ""},
    ]
    for p in payloads:
        response = client.post("/api/v1/auth/register", json=p)
        assert response.status_code == 422

def test_register_duplicate_email(client: TestClient, db_session: Session):
    """Validates duplicate registrations fail with an HTTP 409 Conflict code."""
    payload = {"email": "dup@codeforge.ai", "password": "secure-password-123"}
    
    # First registration
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    
    # Duplicate registration
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert r2.json()["detail"] == "Email address already registered."

def test_login_success(client: TestClient):
    """Validates login with correct credentials returns Bearer access token."""
    # Register user
    reg_payload = {"email": "login@codeforge.ai", "password": "secure-password-123"}
    client.post("/api/v1/auth/register", json=reg_payload)

    # Login user
    login_payload = {"email": "login@codeforge.ai", "password": "secure-password-123"}
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_failures(client: TestClient):
    """Validates login fails generic credentials checks for nonexistent or incorrect entries."""
    reg_payload = {"email": "failure@codeforge.ai", "password": "secure-password-123"}
    client.post("/api/v1/auth/register", json=reg_payload)

    # Wrong password
    r1 = client.post("/api/v1/auth/login", json={"email": "failure@codeforge.ai", "password": "wrong-password"})
    assert r1.status_code == 401
    assert r1.json()["detail"] == "Incorrect email or password"

    # Nonexistent account
    r2 = client.post("/api/v1/auth/login", json={"email": "missing@codeforge.ai", "password": "secure-password-123"})
    assert r2.status_code == 401
    assert r2.json()["detail"] == "Incorrect email or password"

def test_login_inactive_account(client: TestClient, db_session: Session):
    """Validates that logins fail with the same generic error if the account is disabled."""
    reg_payload = {"email": "inactive@codeforge.ai", "password": "secure-password-123"}
    client.post("/api/v1/auth/register", json=reg_payload)

    # Force user profile active flag to False in DB
    user = db_session.query(User).filter(User.email == "inactive@codeforge.ai").first()
    user.is_active = False
    db_session.commit()

    # Login
    response = client.post("/api/v1/auth/login", json={"email": "inactive@codeforge.ai", "password": "secure-password-123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_protected_me_endpoint(client: TestClient):
    """Validates that authenticated requests resolve profiles and unauthenticated fail."""
    # Register and login
    reg_payload = {"email": "me@codeforge.ai", "password": "secure-password-123"}
    client.post("/api/v1/auth/register", json=reg_payload)

    login_resp = client.post("/api/v1/auth/login", json=reg_payload)
    token = login_resp.json()["access_token"]

    # 1. Successful /me fetch
    headers = {"Authorization": f"Bearer {token}"}
    r1 = client.get("/api/v1/auth/me", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["email"] == "me@codeforge.ai"
    assert "password" not in r1.json()

    # 2. Call /me with no token
    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 401 # get_current_user returns 401 if header is missing

    # 3. Call /me with malformed token
    headers_malformed = {"Authorization": "Bearer not-a-valid-token"}
    r3 = client.get("/api/v1/auth/me", headers=headers_malformed)
    assert r3.status_code == 401

def test_jwt_validation_cases(client: TestClient, db_session: Session):
    """Verifies that expired, wrongly signed, wrong algorithm, or missing sub claims are rejected."""
    # Create user to bind tokens to
    user = User(email="jwt@codeforge.ai", hashed_password="pw", is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    user_id = str(user.id)

    # 1. Expired token validation
    expired_token = create_test_token(user_id, expire_minutes=-10)
    headers = {"Authorization": f"Bearer {expired_token}"}
    r1 = client.get("/api/v1/auth/me", headers=headers)
    assert r1.status_code == 401

    # 2. Token with wrong signature
    wrong_sig_token = create_test_token(user_id, secret="wrong_secret_key_value")
    headers = {"Authorization": f"Bearer {wrong_sig_token}"}
    r2 = client.get("/api/v1/auth/me", headers=headers)
    assert r2.status_code == 401

    # 3. Token with wrong algorithm
    wrong_alg_token = create_test_token(user_id, algorithm="HS384")
    headers = {"Authorization": f"Bearer {wrong_alg_token}"}
    r3 = client.get("/api/v1/auth/me", headers=headers)
    assert r3.status_code == 401

    # 4. Token with missing subject claim
    missing_sub_token = create_test_token(user_id, include_sub=False)
    headers = {"Authorization": f"Bearer {missing_sub_token}"}
    r4 = client.get("/api/v1/auth/me", headers=headers)
    assert r4.status_code == 401

    # 5. Token with non-existent user ID
    random_user_id = str(uuid.uuid4())
    nonexistent_token = create_test_token(random_user_id)
    headers = {"Authorization": f"Bearer {nonexistent_token}"}
    r5 = client.get("/api/v1/auth/me", headers=headers)
    assert r5.status_code == 401

    # 6. Inactive user token validation
    inactive_user = User(email="disabled@codeforge.ai", hashed_password="pw", is_active=False)
    db_session.add(inactive_user)
    db_session.commit()
    db_session.refresh(inactive_user)
    
    inactive_token = create_test_token(str(inactive_user.id))
    headers = {"Authorization": f"Bearer {inactive_token}"}
    r6 = client.get("/api/v1/auth/me", headers=headers)
    assert r6.status_code == 401

def test_jwt_secret_mandatory_in_production(monkeypatch):
    """Validates that settings construction fails if JWT_SECRET_KEY is empty in production."""
    from pydantic import ValidationError
    from app.core.config import Settings
    
    # Simulate production environment parameters
    monkeypatch.setenv("FORCE_PROD_CONFIG_CHECK", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ENV", "production")
    
    # Attempt settings load without key
    with pytest.raises(ValidationError) as excinfo:
        Settings(ENV="production", JWT_SECRET_KEY=None)
    assert "JWT_SECRET_KEY must be configured in non-testing environments" in str(excinfo.value)
