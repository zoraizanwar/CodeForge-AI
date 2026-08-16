import uuid
import datetime
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.analytics import AnalyticsRetentionPolicy, UsageRecord
from app.services.authorization.audit_service import AuditService

class RetentionService:
    @staticmethod
    def _to_uuid(val: Any) -> uuid.UUID:
        if isinstance(val, uuid.UUID):
            return val
        return uuid.UUID(str(val))

    @classmethod
    def get_or_create_policy(cls, db: Session, organization_id: Any) -> AnalyticsRetentionPolicy:
        org_uuid = cls._to_uuid(organization_id)
        policy = db.query(AnalyticsRetentionPolicy).filter(AnalyticsRetentionPolicy.organization_id == org_uuid).first()
        if not policy:
            policy = AnalyticsRetentionPolicy(
                organization_id=org_uuid,
                retention_days=90,
                is_enabled=True,
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
        return policy

    @classmethod
    def set_policy(
        cls,
        db: Session,
        organization_id: Any,
        retention_days: int,
        is_enabled: bool = True,
        actor_user_id: Optional[Any] = None,
    ) -> AnalyticsRetentionPolicy:
        org_uuid = cls._to_uuid(organization_id)
        policy = cls.get_or_create_policy(db, org_uuid)
        policy.retention_days = retention_days
        policy.is_enabled = is_enabled
        db.commit()
        db.refresh(policy)

        if actor_user_id:
            AuditService.log_event(
                db=db,
                action="analytics_retention.update",
                status="success",
                user_id=cls._to_uuid(actor_user_id),
                organization_id=org_uuid,
                metadata={"retention_days": retention_days, "is_enabled": is_enabled},
            )

        return policy

    @classmethod
    def cleanup_expired_analytics(cls, db: Session, organization_id: Any) -> int:
        org_uuid = cls._to_uuid(organization_id)
        policy = cls.get_or_create_policy(db, org_uuid)
        if not policy.is_enabled or policy.retention_days <= 0:
            return 0

        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=policy.retention_days)
        
        # Delete old usage records (never touch audit events!)
        deleted_count = db.query(UsageRecord).filter(
            UsageRecord.organization_id == org_uuid,
            UsageRecord.created_at < cutoff
        ).delete()

        policy.last_cleanup_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        return deleted_count
