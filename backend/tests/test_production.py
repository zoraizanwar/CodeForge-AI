"""
Comprehensive Production Readiness & Deployment Test Suite for CodeForge AI Step 13.
Tests production environment validation, health/readiness probes, request correlation,
security headers, global error handling, log secret redaction, and worker process safety.
"""
import os
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import redact_secrets, request_id_ctx
from tests.test_auth import create_test_token


# ─── 1. Production Config Validation & Fast Fail ─────────────────────────

def test_production_config_validation_and_failures():
    """Verifies production mode fails fast when JWT_SECRET_KEY is default/insecure or CORS is wildcard."""
    # Test insecure JWT secret in production
    with pytest.raises(ValueError, match="Production mode requires a strong, non-default JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            ENV="production",
            JWT_SECRET_KEY="dev_secret_key_1234567890_codeforge_foundation",
            FORCE_PROD_CONFIG_CHECK_DISABLE=None
        )

    # Test wildcard CORS in production
    with pytest.raises(ValueError, match="Wildcard CORS_ORIGINS '\\*' is forbidden"):
        Settings(
            ENVIRONMENT="production",
            ENV="production",
            JWT_SECRET_KEY="super_strong_production_secret_key_1234567890!",
            CORS_ORIGINS="*",
            FORCE_PROD_CONFIG_CHECK_DISABLE=None
        )

    # Test valid production configuration
    valid_prod = Settings(
        ENVIRONMENT="production",
        ENV="production",
        JWT_SECRET_KEY="super_strong_production_secret_key_1234567890!",
        CORS_ORIGINS="http://codeforge.local",
        FORCE_PROD_CONFIG_CHECK_DISABLE=None
    )
    assert valid_prod.JWT_SECRET_KEY == "super_strong_production_secret_key_1234567890!"


# ─── 2. Health & Readiness Probes ─────────────────────────────────────────

def test_health_and_readiness_endpoints(client: TestClient):
    """Verifies /health liveness and /ready readiness probes."""
    # Liveness check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["status"] == "ok"
    assert h_data["service"] == "codeforge-ai"

    # Readiness check
    ready_resp = client.get("/ready")
    assert ready_resp.status_code == 200
    r_data = ready_resp.json()
    assert r_data["status"] == "ready"
    assert r_data["services"]["database"] == "ok"
    assert r_data["services"]["workspace"] == "ok"
    assert r_data["services"]["job_queue"] == "ok"


# ─── 3. Request Correlation ID Middleware ─────────────────────────────────

def test_request_correlation_id_middleware(client: TestClient):
    """Verifies X-Request-ID propagation into context logger and response headers."""
    custom_req_id = f"req-test-{uuid.uuid4()}"
    resp = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_req_id

    # Auto-generated ID if missing
    resp_auto = client.get("/health")
    assert resp_auto.status_code == 200
    assert "X-Request-ID" in resp_auto.headers


# ─── 4. Security Headers Middleware ───────────────────────────────────────

def test_production_security_headers_middleware(client: TestClient):
    """Verifies production security headers on all responses."""
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"


# ─── 5. Secret Redaction in Loggers ───────────────────────────────────────

def test_secret_redaction_in_logging():
    """Verifies sensitive keys and tokens are redacted from log messages and extras."""
    sensitive_msg = "User authenticated with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and password Secret123!"
    redacted_msg = redact_secrets(sensitive_msg)
    assert "[REDACTED_LOG_SECRET]" in redacted_msg

    sensitive_dict = {
        "user_email": "test@codeforge.test",
        "jwt_token": "eyJhbGciOiJIUzI1Ni...",
        "db_password": "supersecretpassword",
        "nested": {"github_token": "ghp_1234567890"}
    }
    redacted_dict = redact_secrets(sensitive_dict)
    assert redacted_dict["jwt_token"] == "[REDACTED_LOG_SECRET]"
    assert redacted_dict["db_password"] == "[REDACTED_LOG_SECRET]"
    assert redacted_dict["nested"]["github_token"] == "[REDACTED_LOG_SECRET]"
    assert redacted_dict["user_email"] == "test@codeforge.test"


# ─── 6. Global Exception Handler Sanitization ─────────────────────────────

def test_centralized_error_handling_sanitization(db_session: Session):
    """Verifies unhandled exceptions return structured errors without leaking internal tracebacks or secrets."""
    from app.main import app
    safe_client = TestClient(app, raise_server_exceptions=False)
    token = create_test_token(user_id=str(uuid.uuid4()))
    headers = {"Authorization": f"Bearer {token}"}
    with patch("sqlalchemy.orm.Session.execute", side_effect=RuntimeError("Database Connection Failed: postgres://admin:secret123@db")):
        resp = safe_client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 500
        err_data = resp.json()
        assert err_data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "secret123" not in resp.text
        assert "RuntimeError" not in err_data["message"]
        assert "request_id" in err_data


# ─── 7. Job Worker Shutdown & Safety ──────────────────────────────────────

def test_worker_graceful_shutdown_and_safety():
    """Verifies worker process signals clean shutdown."""
    from app.services.jobs.worker import stop_worker_loop, _WORKER_SHUTDOWN_EVENT
    stop_worker_loop()
    assert _WORKER_SHUTDOWN_EVENT.is_set() is True
