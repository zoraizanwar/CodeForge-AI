import uuid
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.analytics import UsageRecord, UsageQuota, AnalyticsRetentionPolicy, UsageDailyAggregate
from app.services.analytics.usage_service import UsageService
from app.services.analytics.quota_service import QuotaService
from app.services.analytics.aggregation_service import AggregationService
from app.services.analytics.retention_service import RetentionService
from app.services.authorization.permission_service import PermissionService

router = APIRouter()

# Pydantic Schemas
class OverviewResponse(BaseModel):
    total_tokens: int
    estimated_cost: float
    api_requests: int
    execution_pass_rate: float
    webhook_success_rate: float

class QuotaResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    quota_type: str
    limit_value: float
    current_usage: float
    warning_threshold: float
    is_enabled: bool
    reset_period: str
    updated_at: Any

    class Config:
        from_attributes = True

class QuotaUpdate(BaseModel):
    limit_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    is_enabled: Optional[bool] = None

class UsageRecordResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    event_type: str
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: float
    estimated_cost: float
    created_at: Any

    class Config:
        from_attributes = True

class AIUsageSummary(BaseModel):
    provider: str
    model: str
    total_tokens: int
    estimated_cost: float
    total_requests: int

class ReportResponse(BaseModel):
    organization_id: uuid.UUID
    overview: OverviewResponse
    quotas: List[QuotaResponse]
    top_ai_models: List[AIUsageSummary]

# Endpoints
@router.get("/organizations/{org_id}/analytics/overview", response_model=OverviewResponse)
def get_analytics_overview(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    return AggregationService.get_summary_overview(db, org_id)

@router.get("/organizations/{org_id}/analytics/usage", response_model=List[UsageRecordResponse])
def get_analytics_usage(
    org_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = None,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    query = db.query(UsageRecord).filter(UsageRecord.organization_id == org_id)
    if event_type:
        query = query.filter(UsageRecord.event_type == event_type)
    if provider:
        query = query.filter(UsageRecord.provider == provider)
    return query.order_by(UsageRecord.created_at.desc()).limit(limit).all()

@router.get("/organizations/{org_id}/analytics/agents")
def get_agent_analytics(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    agent_usage = (
        db.query(
            UsageRecord.event_type,
            func.count(UsageRecord.id).label("count"),
            func.sum(UsageRecord.duration_ms).label("total_duration")
        )
        .filter(UsageRecord.organization_id == org_id)
        .group_by(UsageRecord.event_type)
        .all()
    )
    return [{"event_type": r.event_type, "count": r.count, "total_duration": r.total_duration or 0.0} for r in agent_usage]

@router.get("/organizations/{org_id}/analytics/repositories")
def get_repository_analytics(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    repo_usage = (
        db.query(
            UsageRecord.repository_id,
            func.count(UsageRecord.id).label("records"),
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("estimated_cost")
        )
        .filter(UsageRecord.organization_id == org_id, UsageRecord.repository_id.isnot(None))
        .group_by(UsageRecord.repository_id)
        .all()
    )
    return [
        {
            "repository_id": str(r.repository_id),
            "records": r.records,
            "total_tokens": r.total_tokens or 0,
            "estimated_cost": round(r.estimated_cost or 0.0, 4)
        }
        for r in repo_usage
    ]

@router.get("/organizations/{org_id}/analytics/ai-usage", response_model=List[AIUsageSummary])
def get_ai_usage_breakdown(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    breakdown = (
        db.query(
            UsageRecord.provider,
            UsageRecord.model,
            func.sum(UsageRecord.total_tokens).label("tokens"),
            func.sum(UsageRecord.estimated_cost).label("cost"),
            func.count(UsageRecord.id).label("requests")
        )
        .filter(UsageRecord.organization_id == org_id, UsageRecord.provider.isnot(None))
        .group_by(UsageRecord.provider, UsageRecord.model)
        .all()
    )
    return [
        AIUsageSummary(
            provider=r.provider or "unknown",
            model=r.model or "unknown",
            total_tokens=int(r.tokens or 0),
            estimated_cost=round(float(r.cost or 0.0), 4),
            total_requests=r.requests
        )
        for r in breakdown
    ]

@router.get("/organizations/{org_id}/analytics/quotas", response_model=List[QuotaResponse])
def get_organization_quotas(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    return QuotaService.get_quotas(db, org_id)

@router.patch("/organizations/{org_id}/analytics/quotas/{quota_id}", response_model=QuotaResponse)
def update_organization_quota(
    org_id: uuid.UUID,
    quota_id: uuid.UUID,
    quota_in: QuotaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    quota = db.query(UsageQuota).filter(UsageQuota.id == quota_id, UsageQuota.organization_id == org_id).first()
    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")

    limit_val = quota_in.limit_value if quota_in.limit_value is not None else quota.limit_value
    warn_thresh = quota_in.warning_threshold if quota_in.warning_threshold is not None else quota.warning_threshold
    enabled = quota_in.is_enabled if quota_in.is_enabled is not None else quota.is_enabled

    updated = QuotaService.set_quota(
        db, org_id, quota.quota_type, limit_val, warn_thresh, enabled, actor_user_id=current_user.id
    )
    return updated

@router.get("/organizations/{org_id}/analytics/report", response_model=ReportResponse)
def get_enterprise_report(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    overview = AggregationService.get_summary_overview(db, org_id)
    quotas = QuotaService.get_quotas(db, org_id)
    ai_breakdown = get_ai_usage_breakdown(org_id, db, current_user)

    return ReportResponse(
        organization_id=org_id,
        overview=OverviewResponse(**overview),
        quotas=[QuotaResponse.model_validate(q) for q in quotas],
        top_ai_models=ai_breakdown
    )
