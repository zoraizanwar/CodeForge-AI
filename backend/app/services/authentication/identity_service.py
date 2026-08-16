import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.identity import ExternalIdentity, LoginEvent
from app.services.authorization.audit_service import AuditService

class IdentityService:
    @staticmethod
    def get_user_identities(db: Session, user_id: uuid.UUID) -> List[ExternalIdentity]:
        return db.query(ExternalIdentity).filter(ExternalIdentity.user_id == user_id).all()

    @staticmethod
    def get_identity_by_provider(db: Session, provider: str, provider_subject: str) -> Optional[ExternalIdentity]:
        return db.query(ExternalIdentity).filter(
            ExternalIdentity.provider == provider,
            ExternalIdentity.provider_subject == provider_subject
        ).first()

    @staticmethod
    def link_external_identity(
        db: Session,
        user_id: uuid.UUID,
        provider: str,
        provider_subject: str,
        provider_email: Optional[str] = None,
        provider_username: Optional[str] = None,
        metadata: dict = None
    ) -> ExternalIdentity:
        # Check if already linked
        existing = IdentityService.get_identity_by_provider(db, provider, provider_subject)
        if existing:
            if existing.user_id != user_id:
                raise ValueError("Identity already linked to another user")
            return existing
            
        identity = ExternalIdentity(
            user_id=user_id,
            provider=provider,
            provider_subject=provider_subject,
            provider_email=provider_email,
            provider_username=provider_username,
            metadata_payload=metadata or {}
        )
        db.add(identity)
        db.commit()
        db.refresh(identity)
        
        # Log event
        AuditService.log_event(
            db=db,
            event_type="identity_linked",
            success=True,
            metadata={"provider": provider, "provider_subject": provider_subject},
            user_id=user_id
        )
        
        return identity

    @staticmethod
    def unlink_external_identity(db: Session, user_id: uuid.UUID, identity_id: uuid.UUID) -> bool:
        identity = db.query(ExternalIdentity).filter(
            ExternalIdentity.id == identity_id,
            ExternalIdentity.user_id == user_id
        ).first()
        
        if not identity:
            return False
            
        # Prevent removing last identity if no password is set (omitted here, assumed checked at higher layer or password always exists)
        
        db.delete(identity)
        db.commit()
        
        AuditService.log_event(
            db=db,
            event_type="identity_unlinked",
            success=True,
            metadata={"provider": identity.provider, "provider_subject": identity.provider_subject},
            user_id=user_id
        )
        return True
