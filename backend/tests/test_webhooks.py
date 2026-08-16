import pytest
from app.models.organization import Organization, OrganizationMember
from app.services.events.webhook_service import WebhookService, SSRFValidationError
from app.services.events.event_publisher import EventPublisher, redact_payload
from app.services.events.delivery_service import WebhookDeliveryService

def test_secret_redaction():
    raw_payload = {
        "user": "alice",
        "password": "supersecretpassword",
        "api_key": "12345",
        "nested": {
            "token": "bearer xyz",
            "safe_field": "hello"
        }
    }
    redacted = redact_payload(raw_payload)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == "hello"

def test_ssrf_protection_blocked_ips():
    blocked_urls = [
        "http://localhost:8000/webhook",
        "http://127.0.0.1/callback",
        "http://10.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/test",
    ]
    for url in blocked_urls:
        with pytest.raises(SSRFValidationError):
            WebhookService.validate_url(url)

def test_ssrf_protection_allowed_url():
    valid_url = "https://example.com/webhooks/receive"
    validated = WebhookService.validate_url(valid_url)
    assert validated == valid_url

def test_webhook_crud_and_secret_rotation(db_session, test_user):
    org = Organization(name="Webhook Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    # Create webhook
    config, secret = WebhookService.create_webhook(
        db=db_session,
        organization_id=str(org.id),
        url="https://example.com/hook",
        description="Test hook",
        subscribed_events=["repo.created", "agent.task_created"]
    )
    assert config.url == "https://example.com/hook"
    assert secret.startswith("whsec_")
    assert config.is_active is True

    # List webhooks
    webhooks = WebhookService.list_webhooks(db_session, str(org.id))
    assert len(webhooks) == 1

    # Update webhook
    updated = WebhookService.update_webhook(
        db_session, str(org.id), str(config.id), description="Updated description", is_active=False
    )
    assert updated.description == "Updated description"
    assert updated.is_active is False

    # Secret rotation
    rotated_cfg, new_secret = WebhookService.rotate_secret(db_session, str(org.id), str(config.id))
    assert new_secret != secret
    assert new_secret.startswith("whsec_")

    # Delete webhook
    deleted = WebhookService.delete_webhook(db_session, str(org.id), str(config.id))
    assert deleted is True

def test_event_publisher_idempotency(db_session, test_user):
    org = Organization(name="Event Org")
    db_session.add(org)
    db_session.commit()

    event1 = EventPublisher.publish_event(
        db=db_session,
        event_type="repo.created",
        organization_id=str(org.id),
        payload={"repo_name": "my-repo"},
        idempotency_key="key-12345"
    )

    event2 = EventPublisher.publish_event(
        db=db_session,
        event_type="repo.created",
        organization_id=str(org.id),
        payload={"repo_name": "my-repo"},
        idempotency_key="key-12345"
    )

    assert event1.id == event2.id

def test_hmac_signature_generation():
    secret = "whsec_0123456789abcdef"
    timestamp = 1600000000
    payload_bytes = b'{"event":"test"}'

    sig = WebhookService.compute_signature(secret, timestamp, payload_bytes)
    assert sig.startswith(f"t={timestamp},v1=")
    assert len(sig.split("v1=")[1]) == 64 # SHA-256 hex length
