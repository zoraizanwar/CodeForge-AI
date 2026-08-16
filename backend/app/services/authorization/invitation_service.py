import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.organization import OrganizationInvitation, OrganizationMember
from app.services.authorization.audit_service import AuditService

class InvitationService:
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def invite_member(cls, db: Session, org_id: uuid.UUID, email: str, role: str, actor_id: uuid.UUID) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(token)
        
        invitation = OrganizationInvitation(
            organization_id=org_id,
            email=email,
            role=role,
            token_hash=token_hash,
            invited_by=actor_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(invitation)
        db.commit()
        
        AuditService.log_event(
            db=db,
            event_type="member_invited",
            
            
            
            success=True,
            organization_id=org_id,
            user_id=actor_id,
            metadata={"email": email, "role": role}
        )
        
        # In a real system, send email here. Return raw token for now.
        return token

    @classmethod
    def accept_invitation(cls, db: Session, token: str, user_id: uuid.UUID, user_email: str):
        token_hash = cls._hash_token(token)
        invitation = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.token_hash == token_hash,
            OrganizationInvitation.revoked_at == None,
            OrganizationInvitation.accepted_at == None,
            OrganizationInvitation.expires_at > datetime.now(timezone.utc)
        ).first()
        
        if not invitation:
            raise HTTPException(status_code=400, detail="Invalid, expired, or revoked invitation.")
            
        if invitation.email != user_email:
            raise HTTPException(status_code=400, detail="Invitation email does not match user email.")
            
        invitation.accepted_at = datetime.now(timezone.utc)
        
        member = OrganizationMember(
            organization_id=invitation.organization_id,
            user_id=user_id,
            role=invitation.role,
            status="active",
            invited_by=invitation.invited_by,
            joined_at=datetime.now(timezone.utc)
        )
        db.add(member)
        db.commit()
        
        AuditService.log_event(
            db=db,
            event_type="invitation_accepted",
            
            
            
            success=True,
            organization_id=invitation.organization_id,
            user_id=user_id
        )

    @classmethod
    def revoke_invitation(cls, db: Session, invitation_id: uuid.UUID, actor_id: uuid.UUID):
        invitation = db.query(OrganizationInvitation).filter(OrganizationInvitation.id == invitation_id).first()
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")
            
        invitation.revoked_at = datetime.now(timezone.utc)
        db.commit()
        
        AuditService.log_event(
            db=db,
            event_type="invitation_revoked",
            
            
            
            success=True,
            organization_id=invitation.organization_id,
            user_id=actor_id
        )
