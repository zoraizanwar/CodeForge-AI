import uuid
from typing import Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.analytics import UsageQuota
from app.services.authorization.audit_service import AuditService

DEFAULT_QUOTAS = {
    "monthly_requests": 100000.0,
    "monthly_agent_runs": 1000.0,
    "monthly_tokens": 10000000.0, # 10M tokens
    "monthly_execution_minutes": 5000.0,
    "monthly_ai_cost": 500.0, # $500
    "concurrent_jobs": 10.0,
}

class QuotaService:
    @staticmethod
    def _to_uuid(val: Any) -> uuid.UUID:
        if isinstance(val, uuid.UUID):
            return val
        return uuid.UUID(str(val))

    @classmethod
    def get_quotas(cls, db: Session, organization_id: Any) -> List[UsageQuota]:
        org_uuid = cls._to_uuid(organization_id)
        quotas = db.query(UsageQuota).filter(UsageQuota.organization_id == org_uuid).all()
        if not quotas:
            # Seed default quotas
            quotas = []
            for q_type, limit_val in DEFAULT_QUOTAS.items():
                q = UsageQuota(
                    organization_id=org_uuid,
                    quota_type=q_type,
                    limit_value=limit_val,
                    current_usage=0.0,
                    warning_threshold=0.8,
                    is_enabled=True,
                )
                db.add(q)
                quotas.append(q)
            db.commit()
            for q in quotas:
                db.refresh(q)
        return quotas

    @classmethod
    def get_quota(cls, db: Session, organization_id: Any, quota_type: str) -> Optional[UsageQuota]:
        org_uuid = cls._to_uuid(organization_id)
        return (
            db.query(UsageQuota)
            .filter(UsageQuota.organization_id == org_uuid, UsageQuota.quota_type == quota_type)
            .first()
        )

    @classmethod
    def set_quota(
        cls,
        db: Session,
        organization_id: Any,
        quota_type: str,
        limit_value: float,
        warning_threshold: float = 0.8,
        is_enabled: bool = True,
        actor_user_id: Optional[Any] = None,
    ) -> UsageQuota:
        org_uuid = cls._to_uuid(organization_id)
        quota = cls.get_quota(db, org_uuid, quota_type)
        if not quota:
            quota = UsageQuota(
                organization_id=org_uuid,
                quota_type=quota_type,
                limit_value=limit_value,
                current_usage=0.0,
                warning_threshold=warning_threshold,
                is_enabled=is_enabled,
            )
            db.add(quota)
        else:
            quota.limit_value = limit_value
            quota.warning_threshold = warning_threshold
            quota.is_enabled = is_enabled

        db.commit()
        db.refresh(quota)

        if actor_user_id:
            AuditService.log_event(
                db=db,
                action="quota.update",
                status="success",
                user_id=cls._to_uuid(actor_user_id),
                organization_id=org_uuid,
                metadata={"quota_type": quota_type, "limit_value": limit_value},
            )

        return quota

    @classmethod
    def check_quota(
        cls, db: Session, organization_id: Any, quota_type: str, increment: float = 1.0
    ) -> Tuple[bool, bool, str]:
        org_uuid = cls._to_uuid(organization_id)
        quota = cls.get_quota(db, org_uuid, quota_type)
        if not quota or not quota.is_enabled:
            return True, False, ""

        projected = quota.current_usage + increment
        if projected > quota.limit_value:
            return False, True, f"Hard limit reached for {quota_type}: {quota.current_usage}/{quota.limit_value}"

        if projected >= (quota.limit_value * quota.warning_threshold):
            return True, True, f"Warning threshold reached for {quota_type}: {quota.current_usage}/{quota.limit_value}"

        return True, False, ""

    @classmethod
    def increment_usage(cls, db: Session, organization_id: Any, quota_type: str, amount: float = 1.0):
        org_uuid = cls._to_uuid(organization_id)
        quota = cls.get_quota(db, org_uuid, quota_type)
        if quota and quota.is_enabled:
            quota.current_usage += amount
            db.commit()
