import uuid
import datetime
from sqlalchemy import Column, String, Boolean, Integer, Float, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base, UTCDateTime

class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    repository_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    description = Column(String(255), nullable=True)
    secret_ciphertext = Column(String(512), nullable=False)
    secret_hash = Column(String(128), nullable=False)
    subscribed_events = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhook_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("system_events.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True) # pending, success, failed, retrying
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    http_status = Column(Integer, nullable=True)
    request_headers = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    response_headers = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    response_body = Column(String(4096), nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    error_message = Column(String(1024), nullable=True)
    next_retry_at = Column(UTCDateTime, nullable=True, index=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
