import uuid
import datetime
from sqlalchemy import Column, String, Boolean, Integer, Float, ForeignKey, JSON, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base, UTCDateTime

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    repository_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    agent_run_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    event_type = Column(String(100), nullable=False, index=True)
    provider = Column(String(100), nullable=True, index=True)
    model = Column(String(100), nullable=True, index=True)
    
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    
    duration_ms = Column(Float, default=0.0, nullable=False)
    estimated_cost = Column(Float, default=0.0, nullable=False)
    
    metadata_payload = Column("metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)


class UsageDailyAggregate(Base):
    __tablename__ = "usage_daily_aggregates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    api_requests = Column(Integer, default=0, nullable=False)
    agent_runs = Column(Integer, default=0, nullable=False)
    successful_runs = Column(Integer, default=0, nullable=False)
    failed_runs = Column(Integer, default=0, nullable=False)
    
    executions = Column(Integer, default=0, nullable=False)
    successful_executions = Column(Integer, default=0, nullable=False)
    failed_executions = Column(Integer, default=0, nullable=False)
    
    repair_attempts = Column(Integer, default=0, nullable=False)
    human_escalations = Column(Integer, default=0, nullable=False)
    pr_creations = Column(Integer, default=0, nullable=False)
    
    webhook_deliveries = Column(Integer, default=0, nullable=False)
    webhook_failures = Column(Integer, default=0, nullable=False)
    
    total_tokens = Column(Integer, default=0, nullable=False)
    estimated_ai_cost = Column(Float, default=0.0, nullable=False)
    compute_duration_ms = Column(Float, default=0.0, nullable=False)
    
    job_retries = Column(Integer, default=0, nullable=False)
    job_cancellations = Column(Integer, default=0, nullable=False)
    
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "date", name="uq_org_daily_aggregate"),
    )


class AgentPerformanceMetric(Base):
    __tablename__ = "agent_performance_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_type = Column(String(100), nullable=False, index=True)
    
    total_runs = Column(Integer, default=0, nullable=False)
    successful_runs = Column(Integer, default=0, nullable=False)
    failed_runs = Column(Integer, default=0, nullable=False)
    
    average_duration_ms = Column(Float, default=0.0, nullable=False)
    average_confidence = Column(Float, default=0.0, nullable=False)
    repair_iterations = Column(Integer, default=0, nullable=False)
    human_escalations = Column(Integer, default=0, nullable=False)
    approval_rate = Column(Float, default=0.0, nullable=False)
    
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "agent_type", name="uq_org_agent_metric"),
    )


class UsageQuota(Base):
    __tablename__ = "usage_quotas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    quota_type = Column(String(100), nullable=False, index=True) # monthly_requests, monthly_agent_runs, monthly_tokens, monthly_execution_minutes, monthly_ai_cost, concurrent_jobs
    
    limit_value = Column(Float, nullable=False)
    current_usage = Column(Float, default=0.0, nullable=False)
    warning_threshold = Column(Float, default=0.8, nullable=False) # e.g. 0.8 = 80%
    is_enabled = Column(Boolean, default=True, nullable=False)
    reset_period = Column(String(50), default="monthly", nullable=False)
    
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "quota_type", name="uq_org_quota_type"),
    )


class AnalyticsRetentionPolicy(Base):
    __tablename__ = "analytics_retention_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    retention_days = Column(Integer, default=90, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_cleanup_at = Column(UTCDateTime, nullable=True)
    
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
