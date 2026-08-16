import uuid
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.event import SystemEvent, WebhookConfig, WebhookDelivery

SENSITIVE_KEYS = {
    "password", "secret", "token", "access_token", "refresh_token",
    "authorization", "private_key", "jwt", "api_key", "client_secret"
}

def redact_payload(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_payload(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_payload(item) for item in data]
    return data

class EventPublisher:
    @staticmethod
    def is_subscribed(subscribed_events: List[str], event_type: str) -> bool:
        if "*" in subscribed_events:
            return True
        if event_type in subscribed_events:
            return True
        for sub in subscribed_events:
            if sub.endswith(".*"):
                prefix = sub[:-2]
                if event_type.startswith(f"{prefix}."):
                    return True
        return False

    @classmethod
    def publish_event(
        cls,
        db: Session,
        event_type: str,
        organization_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        user_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> SystemEvent:
        payload = payload or {}
        redacted = redact_payload(payload)

        if idempotency_key:
            existing = db.query(SystemEvent).filter(SystemEvent.idempotency_key == idempotency_key).first()
            if existing:
                return existing

        org_uuid = uuid.UUID(str(organization_id)) if organization_id else None
        repo_uuid = uuid.UUID(str(repository_id)) if repository_id else None
        user_uuid = uuid.UUID(str(user_id)) if user_id else None

        event = SystemEvent(
            event_type=event_type,
            organization_id=org_uuid,
            repository_id=repo_uuid,
            user_id=user_uuid,
            idempotency_key=idempotency_key,
            payload=redacted,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        if org_uuid:
            webhooks = (
                db.query(WebhookConfig)
                .filter(WebhookConfig.organization_id == org_uuid, WebhookConfig.is_active == True)
                .all()
            )

            for wh in webhooks:
                if cls.is_subscribed(wh.subscribed_events or [], event_type):
                    delivery = WebhookDelivery(
                        webhook_id=wh.id,
                        event_id=event.id,
                        status="pending",
                        attempt_count=0,
                        max_attempts=5,
                    )
                    db.add(delivery)

            db.commit()

        return event
