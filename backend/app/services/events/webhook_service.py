import hashlib
import hmac
import secrets
import socket
import ipaddress
import urllib.parse
from typing import List, Optional, Tuple, Any
from sqlalchemy.orm import Session

from app.models.event import WebhookConfig, WebhookDelivery, SystemEvent

class SSRFValidationError(Exception):
    pass

import uuid

class WebhookService:
    @staticmethod
    def _to_uuid(val: Any) -> uuid.UUID:
        if isinstance(val, uuid.UUID):
            return val
        return uuid.UUID(str(val))

    @staticmethod
    def validate_url(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFValidationError(f"Invalid URL scheme: {parsed.scheme}. Only HTTP/HTTPS supported.")
        
        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("Invalid URL: missing hostname.")

        lower_host = hostname.lower()
        if lower_host in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal") or lower_host.endswith(".local") or lower_host.endswith(".internal"):
            raise SSRFValidationError("SSRF Protection: Requests to localhost or internal hostnames are prohibited.")

        try:
            ip_list = socket.getaddrinfo(hostname, None)
            for item in ip_list:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_multicast
                    or ip_obj.is_reserved
                    or ip_obj.is_unspecified
                ):
                    raise SSRFValidationError(f"SSRF Protection: Destination IP {ip_str} is in a blocked private/loopback/reserved range.")
        except socket.gaierror:
            # If hostname resolution fails, raise SSRF exception or allow depending on mode; raise to be safe
            raise SSRFValidationError(f"Cannot resolve hostname {hostname}.")
        
        return url

    @staticmethod
    def generate_secret() -> Tuple[str, str, str]:
        raw_secret = f"whsec_{secrets.token_hex(24)}"
        secret_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
        # Stored ciphertext (simple obfuscation/encryption for HMAC calculation)
        secret_ciphertext = raw_secret
        return raw_secret, secret_hash, secret_ciphertext

    @staticmethod
    def compute_signature(secret: str, timestamp: int, payload_bytes: bytes) -> str:
        to_sign = f"{timestamp}.".encode("utf-8") + payload_bytes
        sig = hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={sig}"

    @classmethod
    def create_webhook(
        cls,
        db: Session,
        organization_id: Any,
        url: str,
        description: Optional[str] = None,
        subscribed_events: Optional[List[str]] = None,
    ) -> Tuple[WebhookConfig, str]:
        cls.validate_url(url)
        raw_secret, secret_hash, secret_ciphertext = cls.generate_secret()
        org_uuid = cls._to_uuid(organization_id)
        
        config = WebhookConfig(
            organization_id=org_uuid,
            url=url,
            description=description,
            secret_hash=secret_hash,
            secret_ciphertext=secret_ciphertext,
            subscribed_events=subscribed_events or ["*"],
            is_active=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config, raw_secret

    @classmethod
    def list_webhooks(cls, db: Session, organization_id: Any) -> List[WebhookConfig]:
        org_uuid = cls._to_uuid(organization_id)
        return db.query(WebhookConfig).filter(WebhookConfig.organization_id == org_uuid).all()

    @classmethod
    def get_webhook(cls, db: Session, organization_id: Any, webhook_id: Any) -> Optional[WebhookConfig]:
        org_uuid = cls._to_uuid(organization_id)
        wh_uuid = cls._to_uuid(webhook_id)
        return (
            db.query(WebhookConfig)
            .filter(WebhookConfig.id == wh_uuid, WebhookConfig.organization_id == org_uuid)
            .first()
        )

    @classmethod
    def update_webhook(
        cls,
        db: Session,
        organization_id: str,
        webhook_id: str,
        url: Optional[str] = None,
        description: Optional[str] = None,
        subscribed_events: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[WebhookConfig]:
        config = cls.get_webhook(db, organization_id, webhook_id)
        if not config:
            return None
        
        if url is not None:
            cls.validate_url(url)
            config.url = url
        if description is not None:
            config.description = description
        if subscribed_events is not None:
            config.subscribed_events = subscribed_events
        if is_active is not None:
            config.is_active = is_active
            
        db.commit()
        db.refresh(config)
        return config

    @classmethod
    def delete_webhook(cls, db: Session, organization_id: str, webhook_id: str) -> bool:
        config = cls.get_webhook(db, organization_id, webhook_id)
        if not config:
            return False
        db.delete(config)
        db.commit()
        return True

    @classmethod
    def rotate_secret(cls, db: Session, organization_id: str, webhook_id: str) -> Tuple[Optional[WebhookConfig], Optional[str]]:
        config = cls.get_webhook(db, organization_id, webhook_id)
        if not config:
            return None, None
        
        raw_secret, secret_hash, secret_ciphertext = cls.generate_secret()
        config.secret_hash = secret_hash
        config.secret_ciphertext = secret_ciphertext
        db.commit()
        db.refresh(config)
        return config, raw_secret
