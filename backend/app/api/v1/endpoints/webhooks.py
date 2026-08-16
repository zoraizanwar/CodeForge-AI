import uuid
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.event import SystemEvent, WebhookConfig, WebhookDelivery
from app.services.events.webhook_service import WebhookService, SSRFValidationError
from app.services.events.delivery_service import WebhookDeliveryService
from app.services.events.event_publisher import EventPublisher
from app.services.authorization.permission_service import PermissionService
from app.services.authorization.audit_service import AuditService

router = APIRouter()

# Pydantic Schemas
class WebhookCreate(BaseModel):
    url: str
    description: Optional[str] = None
    subscribed_events: Optional[List[str]] = ["*"]

class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    description: Optional[str] = None
    subscribed_events: Optional[List[str]] = None
    is_active: Optional[bool] = None

class WebhookResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    url: str
    description: Optional[str] = None
    subscribed_events: List[str]
    is_active: bool
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True

class WebhookCreateResponse(WebhookResponse):
    secret: str

class SecretRotateResponse(BaseModel):
    webhook_id: uuid.UUID
    secret: str

class SystemEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    organization_id: Optional[uuid.UUID] = None
    repository_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    idempotency_key: Optional[str] = None
    payload: Any
    created_at: Any

    class Config:
        from_attributes = True

class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    event_id: uuid.UUID
    status: str
    attempt_count: int
    max_attempts: int
    http_status: Optional[int] = None
    request_headers: Optional[Any] = None
    response_headers: Optional[Any] = None
    response_body: Optional[str] = None
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    next_retry_at: Optional[Any] = None
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True

# Endpoints
@router.post("/organizations/{org_id}/webhooks", response_model=WebhookCreateResponse)
def create_webhook(
    org_id: uuid.UUID,
    wh_in: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    try:
        config, secret = WebhookService.create_webhook(
            db, str(org_id), wh_in.url, wh_in.description, wh_in.subscribed_events
        )
    except SSRFValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    AuditService.log_event(
        db=db,
        action="webhook.create",
        status="success",
        user_id=current_user.id,
        organization_id=org_id,
        metadata={"webhook_id": str(config.id), "url": config.url},
    )
    res = WebhookCreateResponse.model_validate(config)
    res.secret = secret
    return res

@router.get("/organizations/{org_id}/webhooks", response_model=List[WebhookResponse])
def list_webhooks(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    configs = WebhookService.list_webhooks(db, str(org_id))
    return configs

@router.get("/organizations/{org_id}/webhooks/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    config = WebhookService.get_webhook(db, str(org_id), str(webhook_id))
    if not config:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return config

@router.patch("/organizations/{org_id}/webhooks/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    wh_in: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    try:
        config = WebhookService.update_webhook(
            db, str(org_id), str(webhook_id), wh_in.url, wh_in.description, wh_in.subscribed_events, wh_in.is_active
        )
    except SSRFValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not config:
        raise HTTPException(status_code=404, detail="Webhook not found")

    AuditService.log_event(
        db=db,
        action="webhook.update",
        status="success",
        user_id=current_user.id,
        organization_id=org_id,
        metadata={"webhook_id": str(webhook_id)},
    )
    return config

@router.delete("/organizations/{org_id}/webhooks/{webhook_id}")
def delete_webhook(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    deleted = WebhookService.delete_webhook(db, str(org_id), str(webhook_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")

    AuditService.log_event(
        db=db,
        action="webhook.delete",
        status="success",
        user_id=current_user.id,
        organization_id=org_id,
        metadata={"webhook_id": str(webhook_id)},
    )
    return {"message": "Webhook deleted"}

@router.post("/organizations/{org_id}/webhooks/{webhook_id}/rotate-secret", response_model=SecretRotateResponse)
def rotate_webhook_secret(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    config, secret = WebhookService.rotate_secret(db, str(org_id), str(webhook_id))
    if not config or not secret:
        raise HTTPException(status_code=404, detail="Webhook not found")

    AuditService.log_event(
        db=db,
        action="webhook.rotate_secret",
        status="success",
        user_id=current_user.id,
        organization_id=org_id,
        metadata={"webhook_id": str(webhook_id)},
    )
    return {"webhook_id": config.id, "secret": secret}

@router.post("/organizations/{org_id}/webhooks/{webhook_id}/test", response_model=WebhookDeliveryResponse)
def test_webhook(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    webhook = WebhookService.get_webhook(db, str(org_id), str(webhook_id))
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_event = EventPublisher.publish_event(
        db=db,
        event_type="webhook.test",
        organization_id=str(org_id),
        user_id=str(current_user.id),
        payload={"message": "Test ping event from CodeForge AI"},
    )

    delivery = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.webhook_id == webhook.id, WebhookDelivery.event_id == test_event.id)
        .first()
    )
    if delivery:
        executed_delivery = WebhookDeliveryService.execute_delivery(db, str(delivery.id))
        return executed_delivery
    else:
        raise HTTPException(status_code=500, detail="Failed to create test webhook delivery")

@router.get("/organizations/{org_id}/events", response_model=List[SystemEventResponse])
def list_system_events(
    org_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    events = (
        db.query(SystemEvent)
        .filter(SystemEvent.organization_id == org_id)
        .order_by(SystemEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return events

@router.get("/organizations/{org_id}/events/{event_id}", response_model=SystemEventResponse)
def get_system_event(
    org_id: uuid.UUID,
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    event = (
        db.query(SystemEvent)
        .filter(SystemEvent.id == event_id, SystemEvent.organization_id == org_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="System event not found")
    return event

@router.get("/organizations/{org_id}/webhooks/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
def list_webhook_deliveries(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "viewer")
    webhook = WebhookService.get_webhook(db, str(org_id), str(webhook_id))
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
        .all()
    )
    return deliveries
