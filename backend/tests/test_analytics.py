import pytest
import datetime
from app.models.organization import Organization
from app.services.analytics.usage_service import UsageService
from app.services.analytics.pricing import calculate_ai_cost
from app.services.analytics.quota_service import QuotaService
from app.services.analytics.aggregation_service import AggregationService
from app.services.analytics.retention_service import RetentionService

def test_pricing_calculation():
    # Test Claude 3.5 Sonnet: 1,000 in ($0.003), 1,000 out ($0.015) => $0.018
    cost_claude = calculate_ai_cost("anthropic", "claude-3-5-sonnet", 1000, 1000)
    assert cost_claude == 0.018

    # Test GPT-4o-mini: 10,000 in ($0.0015), 10,000 out ($0.006) => $0.0075
    cost_gpt = calculate_ai_cost("openai", "gpt-4o-mini", 10000, 10000)
    assert cost_gpt == 0.0075

def test_usage_recording_and_redaction(db_session, test_user):
    org = Organization(name="Analytics Org")
    db_session.add(org)
    db_session.commit()

    record = UsageService.record_ai_usage(
        db=db_session,
        organization_id=org.id,
        provider="anthropic",
        model="claude-3-5-sonnet",
        input_tokens=500,
        output_tokens=500,
        duration_ms=1200.0,
        user_id=test_user.id,
        metadata={"prompt_preview": "Hello", "api_key": "secret_key_123"}
    )

    assert record is not None
    assert record.total_tokens == 1000
    assert record.estimated_cost == 0.009
    assert record.metadata_payload["api_key"] == "[REDACTED]"
    assert record.metadata_payload["prompt_preview"] == "Hello"

def test_usage_service_failure_isolation(db_session):
    # Passing invalid organization_id shouldn't throw error
    record = UsageService.record_usage(
        db=db_session,
        organization_id="invalid-uuid",
        event_type="test"
    )
    assert record is None

def test_quota_service_checks(db_session, test_user):
    org = Organization(name="Quota Org")
    db_session.add(org)
    db_session.commit()

    quotas = QuotaService.get_quotas(db_session, org.id)
    assert len(quotas) > 0

    QuotaService.set_quota(db_session, org.id, "monthly_agent_runs", 10.0, warning_threshold=0.8, is_enabled=True)

    # Usage = 0/10 -> allowed=True, warning=False
    allowed, warn, msg = QuotaService.check_quota(db_session, org.id, "monthly_agent_runs", increment=1.0)
    assert allowed is True
    assert warn is False

    # Increment usage to 8 -> warning threshold reached
    QuotaService.increment_usage(db_session, org.id, "monthly_agent_runs", amount=8.0)
    allowed, warn, msg = QuotaService.check_quota(db_session, org.id, "monthly_agent_runs", increment=1.0)
    assert allowed is True
    assert warn is True
    assert "Warning threshold" in msg

    # Increment usage to 11 -> hard limit reached
    QuotaService.increment_usage(db_session, org.id, "monthly_agent_runs", amount=3.0)
    allowed, warn, msg = QuotaService.check_quota(db_session, org.id, "monthly_agent_runs", increment=1.0)
    assert allowed is False
    assert warn is True
    assert "Hard limit reached" in msg

def test_aggregation_summary(db_session, test_user):
    org = Organization(name="Summary Org")
    db_session.add(org)
    db_session.commit()

    UsageService.record_ai_usage(
        db=db_session,
        organization_id=org.id,
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=2000,
        user_id=test_user.id
    )

    overview = AggregationService.get_summary_overview(db_session, org.id)
    assert overview["total_tokens"] == 3000
    assert overview["estimated_cost"] > 0.0

def test_analytics_retention_cleanup(db_session):
    org = Organization(name="Retention Org")
    db_session.add(org)
    db_session.commit()

    RetentionService.set_policy(db_session, org.id, retention_days=30, is_enabled=True)
    
    # Old usage record
    old_record = UsageService.record_usage(
        db=db_session,
        organization_id=org.id,
        event_type="old_event"
    )
    old_record.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
    db_session.commit()

    deleted = RetentionService.cleanup_expired_analytics(db_session, org.id)
    assert deleted == 1
