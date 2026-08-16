import uuid
import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.analytics import UsageRecord
from app.services.events.event_publisher import redact_payload
from app.services.analytics.pricing import calculate_ai_cost

logger = logging.getLogger(__name__)

class UsageService:
    @staticmethod
    def _to_uuid(val: Any) -> Optional[uuid.UUID]:
        if not val:
            return None
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val))
        except Exception:
            return None

    @classmethod
    def record_usage(
        cls,
        db: Session,
        organization_id: Any,
        event_type: str,
        user_id: Optional[Any] = None,
        repository_id: Optional[Any] = None,
        agent_run_id: Optional[Any] = None,
        job_id: Optional[Any] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: Optional[int] = None,
        duration_ms: float = 0.0,
        estimated_cost: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[UsageRecord]:
        try:
            org_uuid = cls._to_uuid(organization_id)
            if not org_uuid:
                return None

            if idempotency_key:
                existing = db.query(UsageRecord).filter(UsageRecord.idempotency_key == idempotency_key).first()
                if existing:
                    return existing

            calc_total_tokens = total_tokens if total_tokens is not None else (input_tokens + output_tokens)
            
            if estimated_cost is None and provider and model:
                cost = calculate_ai_cost(provider, model, input_tokens, output_tokens)
            else:
                cost = estimated_cost or 0.0

            clean_meta = redact_payload(metadata or {})

            record = UsageRecord(
                organization_id=org_uuid,
                user_id=cls._to_uuid(user_id),
                repository_id=cls._to_uuid(repository_id),
                agent_run_id=cls._to_uuid(agent_run_id),
                job_id=cls._to_uuid(job_id),
                event_type=event_type,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=calc_total_tokens,
                duration_ms=duration_ms,
                estimated_cost=cost,
                metadata_payload=clean_meta,
                idempotency_key=idempotency_key,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
        except Exception as exc:
            logger.warning(f"Analytics failure isolated: {str(exc)}")
            db.rollback()
            return None

    @classmethod
    def record_ai_usage(
        cls,
        db: Session,
        organization_id: Any,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float = 0.0,
        user_id: Optional[Any] = None,
        repository_id: Optional[Any] = None,
        agent_run_id: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UsageRecord]:
        return cls.record_usage(
            db=db,
            organization_id=organization_id,
            event_type="ai_completion",
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            user_id=user_id,
            repository_id=repository_id,
            agent_run_id=agent_run_id,
            metadata=metadata,
        )

    @classmethod
    def record_api_usage(
        cls,
        db: Session,
        organization_id: Any,
        endpoint: str,
        user_id: Optional[Any] = None,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UsageRecord]:
        meta = metadata or {}
        meta["endpoint"] = endpoint
        return cls.record_usage(
            db=db,
            organization_id=organization_id,
            event_type="api_request",
            user_id=user_id,
            duration_ms=duration_ms,
            metadata=meta,
        )

    @classmethod
    def record_job_usage(
        cls,
        db: Session,
        organization_id: Any,
        job_id: Any,
        job_type: str,
        duration_ms: float = 0.0,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UsageRecord]:
        meta = metadata or {}
        meta["job_type"] = job_type
        meta["status"] = status
        return cls.record_usage(
            db=db,
            organization_id=organization_id,
            job_id=job_id,
            event_type="job_execution",
            duration_ms=duration_ms,
            metadata=meta,
        )

    @classmethod
    def record_execution_usage(
        cls,
        db: Session,
        organization_id: Any,
        repository_id: Optional[Any] = None,
        duration_ms: float = 0.0,
        status: str = "passed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UsageRecord]:
        meta = metadata or {}
        meta["status"] = status
        return cls.record_usage(
            db=db,
            organization_id=organization_id,
            repository_id=repository_id,
            event_type="code_execution",
            duration_ms=duration_ms,
            metadata=meta,
        )
