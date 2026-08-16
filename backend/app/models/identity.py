import uuid
import datetime
from sqlalchemy import Column, String, Boolean, ForeignKey, Index, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base, UTCDateTime

class ExternalIdentity(Base):
    __tablename__ = "external_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(100), nullable=False)
    provider_subject = Column(String(255), nullable=False)
    provider_email = Column(String(320), nullable=True)
    provider_username = Column(String(255), nullable=True)
    metadata_payload = Column("metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True)
    last_login_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_external_identity_provider_subject"),
    )

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, index=True)
    refresh_token_hash = Column(String(128), nullable=True, index=True)
    expires_at = Column(UTCDateTime, nullable=False, index=True)
    refresh_expires_at = Column(UTCDateTime, nullable=False)
    revoked_at = Column(UTCDateTime, nullable=True)
    last_used_at = Column(UTCDateTime, nullable=True)
    ip_hash = Column(String(128), nullable=True)
    user_agent_hash = Column(String(128), nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

class LoginEvent(Base):
    __tablename__ = "login_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    provider = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    ip_hash = Column(String(128), nullable=True)
    user_agent_hash = Column(String(128), nullable=True)
    request_id = Column(String(128), nullable=True)
    metadata_payload = Column("metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)

class OrganizationIdentityPolicy(Base):
    __tablename__ = "organization_identity_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)
    allowed_providers = Column(JSON().with_variant(JSONB, "postgresql"), default=list)
    require_sso = Column(Boolean, default=False, nullable=False)
    allow_password_login = Column(Boolean, default=True, nullable=False)
    auto_join_domain = Column(String(320), nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

