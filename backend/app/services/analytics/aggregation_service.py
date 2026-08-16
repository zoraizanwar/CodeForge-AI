import uuid
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.analytics import UsageRecord, UsageDailyAggregate, AgentPerformanceMetric
from app.models.event import WebhookDelivery, SystemEvent

class AggregationService:
    @staticmethod
    def _to_uuid(val: Any) -> uuid.UUID:
        if isinstance(val, uuid.UUID):
            return val
        return uuid.UUID(str(val))

    @classmethod
    def aggregate_daily_metrics(cls, db: Session, organization_id: Any, target_date: Optional[datetime.date] = None) -> UsageDailyAggregate:
        org_uuid = cls._to_uuid(organization_id)
        if not target_date:
            target_date = datetime.datetime.now(datetime.timezone.utc).date()

        start_dt = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=datetime.timezone.utc)
        end_dt = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=datetime.timezone.utc)

        # Query UsageRecords for tokens, costs, compute duration, api requests
        usage_stats = db.query(
            func.count(UsageRecord.id).label("total_records"),
            func.sum(UsageRecord.total_tokens).label("sum_tokens"),
            func.sum(UsageRecord.estimated_cost).label("sum_cost"),
            func.sum(UsageRecord.duration_ms).label("sum_duration"),
        ).filter(
            UsageRecord.organization_id == org_uuid,
            UsageRecord.created_at >= start_dt,
            UsageRecord.created_at <= end_dt
        ).first()

        api_reqs = db.query(func.count(UsageRecord.id)).filter(
            UsageRecord.organization_id == org_uuid,
            UsageRecord.event_type == "api_request",
            UsageRecord.created_at >= start_dt,
            UsageRecord.created_at <= end_dt
        ).scalar() or 0

        # Upsert UsageDailyAggregate
        agg = db.query(UsageDailyAggregate).filter(
            UsageDailyAggregate.organization_id == org_uuid,
            UsageDailyAggregate.date == target_date
        ).first()

        if not agg:
            agg = UsageDailyAggregate(
                organization_id=org_uuid,
                date=target_date,
            )
            db.add(agg)

        agg.api_requests = api_reqs
        agg.total_tokens = int(usage_stats.sum_tokens or 0)
        agg.estimated_ai_cost = float(usage_stats.sum_cost or 0.0)
        agg.compute_duration_ms = float(usage_stats.sum_duration or 0.0)

        db.commit()
        db.refresh(agg)
        return agg

    @classmethod
    def get_summary_overview(cls, db: Session, organization_id: Any) -> Dict[str, Any]:
        org_uuid = cls._to_uuid(organization_id)

        totals = db.query(
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("total_cost"),
            func.count(UsageRecord.id).label("total_records")
        ).filter(UsageRecord.organization_id == org_uuid).first()

        api_count = db.query(func.count(UsageRecord.id)).filter(
            UsageRecord.organization_id == org_uuid,
            UsageRecord.event_type == "api_request"
        ).scalar() or 0

        exec_total = db.query(func.count(UsageRecord.id)).filter(
            UsageRecord.organization_id == org_uuid,
            UsageRecord.event_type == "code_execution"
        ).scalar() or 0

        exec_pass_rate = 1.0

        wh_total = db.query(func.count(WebhookDelivery.id)).join(SystemEvent, WebhookDelivery.event_id == SystemEvent.id).filter(SystemEvent.organization_id == org_uuid).scalar() or 0
        wh_success = db.query(func.count(WebhookDelivery.id)).join(SystemEvent, WebhookDelivery.event_id == SystemEvent.id).filter(SystemEvent.organization_id == org_uuid, WebhookDelivery.status == "success").scalar() or 0
        wh_success_rate = (wh_success / wh_total) if wh_total > 0 else 1.0

        return {
          "total_tokens": int(totals.total_tokens or 0),
          "estimated_cost": round(float(totals.total_cost or 0.0), 4),
          "api_requests": api_count,
          "execution_pass_rate": round(exec_pass_rate, 4),
          "webhook_success_rate": round(wh_success_rate, 4),
        }
