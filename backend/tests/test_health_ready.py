import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app.main import app
from app.models.user import User
from app.core.database import get_db

def test_health(client):
    """Validates /health responds with 200 OK liveness parameters."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data

def test_ready_success(client):
    """Validates /ready responds with 200 OK when database is accessible."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["services"]["database"] == "ok"

def test_ready_db_down(client):
    """Validates /ready responds with 503 Service Unavailable if database is unreachable."""
    class MockSession:
        def execute(self, *args, **kwargs):
            raise Exception("OperationalError: database connection timeout")
        def close(self):
            pass

    def get_db_down_mock():
        yield MockSession()

    app.dependency_overrides[get_db] = get_db_down_mock
    try:
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["database"] == "error"
    finally:
        # Clear dependency overrides after checking failure condition
        app.dependency_overrides.clear()

def test_user_model_creation(db_session):
    """Validates user creation, uuid auto-generation, default flags, and timezone-aware timestamps."""
    new_user = User(
        email="dev@codeforge.ai",
        hashed_password="hashed_string_placeholder"
    )
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)

    assert isinstance(new_user.id, uuid.UUID)
    assert new_user.email == "dev@codeforge.ai"
    assert new_user.hashed_password == "hashed_string_placeholder"
    assert new_user.is_active is True
    assert isinstance(new_user.created_at, datetime)
    assert new_user.created_at.tzinfo == timezone.utc
    assert isinstance(new_user.updated_at, datetime)
    assert new_user.updated_at.tzinfo == timezone.utc

def test_user_email_uniqueness(db_session):
    """Validates that database uniqueness constraints are enforced on the email field."""
    user1 = User(email="test@codeforge.ai", hashed_password="pw")
    db_session.add(user1)
    db_session.commit()

    user2 = User(email="test@codeforge.ai", hashed_password="pw2")
    db_session.add(user2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()
