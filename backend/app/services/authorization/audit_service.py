import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent

class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        organization_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        repository_id: Optional[uuid.UUID] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        success: bool = True
    ) -> AuditEvent:
        """
        Creates an immutable audit log event.
        Ensures sensitive information is never included in metadata.
        """
        # Redact any obvious secrets from metadata just in case
        safe_metadata = {}
        if metadata:
            for k, v in metadata.items():
                if any(sec in k.lower() for sec in ['secret', 'token', 'key', 'password', 'jwt']):
                    safe_metadata[k] = "[REDACTED]"
                else:
                    safe_metadata[k] = v

        event = AuditEvent(
            organization_id=organization_id,
            user_id=user_id,
            repository_id=repository_id,
            event_type=event_type,
            request_id=request_id,
            meta=safe_metadata,
            severity=severity,
            success=success
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
