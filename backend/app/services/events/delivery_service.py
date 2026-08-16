import json
import time
import datetime
import random
import urllib.parse
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from app.models.event import WebhookDelivery, WebhookConfig, SystemEvent
from app.services.events.webhook_service import WebhookService, SSRFValidationError

import uuid

class WebhookDeliveryService:
    @classmethod
    def execute_delivery(cls, db: Session, delivery_id: Any) -> WebhookDelivery:
        del_uuid = delivery_id if isinstance(delivery_id, uuid.UUID) else uuid.UUID(str(delivery_id))
        delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == del_uuid).first()
        if not delivery:
            raise ValueError(f"WebhookDelivery {delivery_id} not found")

        webhook = db.query(WebhookConfig).filter(WebhookConfig.id == delivery.webhook_id).first()
        event = db.query(SystemEvent).filter(SystemEvent.id == delivery.event_id).first()

        if not webhook or not event or not webhook.is_active:
            delivery.status = "failed"
            delivery.error_message = "Webhook or Event missing, or Webhook inactive"
            db.commit()
            return delivery

        # Validate URL for SSRF
        try:
            WebhookService.validate_url(webhook.url)
        except SSRFValidationError as exc:
            delivery.status = "failed"
            delivery.error_message = f"SSRF Blocked: {str(exc)}"
            db.commit()
            return delivery

        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        payload_dict = {
            "id": str(event.id),
            "event": event.event_type,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "organization_id": str(event.organization_id) if event.organization_id else None,
            "repository_id": str(event.repository_id) if event.repository_id else None,
            "data": event.payload,
        }
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode("utf-8")
        signature = WebhookService.compute_signature(webhook.secret_ciphertext, timestamp, payload_bytes)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CodeForge-Webhook/1.0",
            "X-CodeForge-Event": event.event_type,
            "X-CodeForge-Delivery": str(delivery.id),
            "X-CodeForge-Timestamp": str(timestamp),
            "X-CodeForge-Signature": signature,
        }

        delivery.attempt_count += 1
        delivery.request_headers = headers

        start_time = time.time()
        try:
            with httpx.Client(timeout=10.0, follow_redirects=False) as client:
                resp = client.post(webhook.url, content=payload_bytes, headers=headers)
                elapsed_ms = (time.time() - start_time) * 1000.0

                delivery.execution_time_ms = elapsed_ms
                delivery.http_status = resp.status_code
                delivery.response_headers = dict(resp.headers)
                delivery.response_body = resp.text[:4096] if resp.text else ""

                if 200 <= resp.status_code < 300:
                    delivery.status = "success"
                    delivery.error_message = None
                    delivery.next_retry_at = None
                else:
                    is_transient = resp.status_code in (408, 429) or resp.status_code >= 500
                    if is_transient and delivery.attempt_count < delivery.max_attempts:
                        delivery.status = "retrying"
                        backoff = min(3600, (2 ** delivery.attempt_count) * 5 + random.randint(1, 5))
                        delivery.next_retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=backoff)
                        delivery.error_message = f"HTTP {resp.status_code} - Transient failure (attempt {delivery.attempt_count}/{delivery.max_attempts})"
                    else:
                        delivery.status = "failed"
                        delivery.next_retry_at = None
                        delivery.error_message = f"HTTP {resp.status_code} - Permanent failure"

        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000.0
            delivery.execution_time_ms = elapsed_ms
            delivery.http_status = None
            delivery.error_message = f"Connection error: {str(exc)}"

            if delivery.attempt_count < delivery.max_attempts:
                delivery.status = "retrying"
                backoff = min(3600, (2 ** delivery.attempt_count) * 5 + random.randint(1, 5))
                delivery.next_retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=backoff)
            else:
                delivery.status = "failed"
                delivery.next_retry_at = None

        db.commit()
        db.refresh(delivery)
        return delivery
