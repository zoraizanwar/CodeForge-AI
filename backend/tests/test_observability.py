"""
Comprehensive Production Observability, Metrics, Audit Logging & System Monitoring Test Suite (Step 14).
"""
import uuid
import datetime
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User
from app.models.repository import Repository
from app.services.audit import (
    record_event,
    record_security_event,
    record_agent_event,
    record_job_event,
    record_repository_event,
    record_git_event,
    sanitize_audit_metadata,
    MAX_METADATA_BYTES,
)
from app.services.audit_cleanup import cleanup_expired_audit_events
from app.core.metrics import metrics_collector, MetricsCollector
from app.core.error_classifier import classify_error, ERROR_CATEGORIES
from tests.test_auth import create_test_token


# ─── 1. Audit Event Creation & Secret Redaction ─────────────────────────────

def test_audit_event_creation_and_secret_redaction(db_session: Session):
    """Verifies audit event creation with automatic secret redaction."""
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    event = record_event(
        db=db_session,
        event_type="test.audit_event",
        severity="info",
        user_id=user_id,
        repository_id=repo_id,
        request_id="req-test-123",
        success=True,
        metadata={
            "action": "test_action",
            "secret_key": "secret_token_value_12345",
            "password": "my_super_secret_password",
            "normal_field": "public_data"
        }
    )

    assert event is not None
    assert event.event_type == "test.audit_event"
    assert event.severity == "info"
    assert event.request_id == "req-test-123"
    assert event.meta["normal_field"] == "public_data"
    assert event.meta["secret_key"] == "[REDACTED_LOG_SECRET]"
    assert event.meta["password"] == "[REDACTED_LOG_SECRET]"


# ─── 2. Audit Metadata Size Bounds ──────────────────────────────────────────

def test_audit_metadata_size_bounds():
    """Verifies that large metadata payloads exceeding 10KB are truncated safely."""
    huge_metadata = {"data": "x" * 20000}
    sanitized = sanitize_audit_metadata(huge_metadata)

    assert sanitized is not None
    assert sanitized.get("_truncated") is True
    assert "summary" in sanitized


# ─── 3. Audit API & Strict Tenant Isolation ─────────────────────────────────

def test_audit_api_tenant_isolation_and_filtering(client: TestClient, db_session: Session):
    """Verifies that users can only retrieve their own audit records and filter by severity/event_type."""
    user1 = User(id=uuid.uuid4(), email="user1_audit@example.com", hashed_password="pw")
    user2 = User(id=uuid.uuid4(), email="user2_audit@example.com", hashed_password="pw")
    db_session.add_all([user1, user2])
    db_session.commit()

    # Record event for user1
    record_event(db=db_session, event_type="security.path_traversal", severity="warning", user_id=user1.id, success=False)
    record_event(db=db_session, event_type="agent.plan_created", severity="info", user_id=user1.id, success=True)
    
    # Record event for user2
    record_event(db=db_session, event_type="security.unauthorized_access", severity="critical", user_id=user2.id, success=False)

    token1 = create_test_token(user_id=str(user1.id))
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Fetch audit events for user1
    resp = client.get("/api/v1/audit", headers=headers1)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["user_id"] == str(user1.id)

    # Filter by severity=warning
    resp_warn = client.get("/api/v1/audit?severity=warning", headers=headers1)
    assert resp_warn.status_code == 200
    data_warn = resp_warn.json()
    assert data_warn["total"] == 1
    assert data_warn["items"][0]["event_type"] == "security.path_traversal"


# ─── 4. Metrics Endpoint & Authorization ────────────────────────────────────

def test_metrics_endpoint(client: TestClient, db_session: Session):
    """Verifies /metrics endpoint returns aggregated operational statistics for authenticated users."""
    user = User(id=uuid.uuid4(), email="metrics_user@example.com", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    token = create_test_token(user_id=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Unauthenticated request fails
    unauth_resp = client.get("/metrics")
    assert unauth_resp.status_code == 401

    # Authenticated request succeeds
    resp = client.get("/metrics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "http" in data
    assert "jobs" in data
    assert "agents" in data
    assert "repositories" in data
    assert "executions" in data
    assert "git_and_pr" in data
    assert "ai_provider" in data
    assert "websockets" in data


# ─── 5. System Stats API Endpoint ───────────────────────────────────────────

def test_system_stats_endpoint(client: TestClient, db_session: Session):
    """Verifies /api/v1/system/stats returns user-scoped stats and recent security events."""
    user = User(id=uuid.uuid4(), email="stats_user@example.com", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    record_security_event(db=db_session, event_type="test_violation", user_id=user.id, severity="warning")

    token = create_test_token(user_id=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/system/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp" in data
    assert "metrics" in data
    assert "user_stats" in data
    assert data["user_stats"]["repositories"] >= 0
    assert len(data["user_stats"]["security_events"]) == 1


# ─── 6. Audit Retention Cleanup Service ─────────────────────────────────────

def test_audit_cleanup_service(db_session: Session):
    """Verifies audit event cleanup purges records older than retention period and supports dry_run."""
    user_id = uuid.uuid4()

    # Create old event (40 days ago)
    old_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=40)
    old_event = AuditEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        event_type="old.event",
        severity="info",
        created_at=old_date
    )
    # Create recent event (2 days ago)
    recent_event = AuditEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        event_type="recent.event",
        severity="info",
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add_all([old_event, recent_event])
    db_session.commit()

    # Dry run cleanup (30 days retention)
    dry_res = cleanup_expired_audit_events(db=db_session, retention_days=30, dry_run=True)
    assert dry_res["deleted_count"] == 1
    assert dry_res["dry_run"] is True

    # Real cleanup (30 days retention)
    real_res = cleanup_expired_audit_events(db=db_session, retention_days=30, dry_run=False)
    assert real_res["deleted_count"] == 1

    # Verify old event deleted, recent event remains
    remaining = db_session.query(AuditEvent).filter(AuditEvent.user_id == user_id).all()
    assert len(remaining) == 1
    assert remaining[0].event_type == "recent.event"


# ─── 7. Standardized Error Classification ───────────────────────────────────

def test_error_classification():
    """Verifies error_classifier maps errors to the 14 standardized categories."""
    assert classify_error("JWT token expired") == "authentication"
    assert classify_error("Tenant isolation access denied") == "authorization"
    assert classify_error("Invalid payload value_error") == "validation"
    assert classify_error("Zip bomb detected in archive") == "security"
    assert classify_error("Git push failed to remote branch") == "git"
    assert classify_error("Grok API response timeout") == "ai_provider"
    assert classify_error("pytest sandbox execution timeout") == "execution"
    assert classify_error("Worker claimed job retry limit exceeded") == "job"
    assert classify_error("Unknown random error message") == "unknown"


# ─── 8. Helper Recording Functions ───────────────────────────────────────────

def test_helper_record_functions(db_session: Session):
    """Verifies helper functions (security, agent, job, repository, git)."""
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()

    ev1 = record_security_event(db=db_session, event_type="path_traversal", user_id=u_id)
    assert ev1.event_type == "security.path_traversal"

    ev2 = record_agent_event(db=db_session, event_type="plan_created", user_id=u_id, repository_id=r_id)
    assert ev2.event_type == "agent.plan_created"

    ev3 = record_job_event(db=db_session, event_type="started", job_id=uuid.uuid4(), user_id=u_id)
    assert ev3.event_type == "job.started"

    ev4 = record_repository_event(db=db_session, event_type="imported", repository_id=r_id, user_id=u_id)
    assert ev4.event_type == "repository.imported"

    ev5 = record_git_event(db=db_session, event_type="pr_created", user_id=u_id, repository_id=r_id)
    assert ev5.event_type == "git.pr_created"
