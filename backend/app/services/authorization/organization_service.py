import uuid
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.organization import Organization, OrganizationMember
from app.services.authorization.audit_service import AuditService

class OrganizationService:
    @staticmethod
    def create_organization(db: Session, name: str, slug: str, owner_id: uuid.UUID) -> Organization:
        org = Organization(name=name, slug=slug, owner_id=owner_id)
        db.add(org)
        db.flush()
        
        member = OrganizationMember(
            organization_id=org.id,
            user_id=owner_id,
            role="owner",
            status="active"
        )
        db.add(member)
        db.commit()
        db.refresh(org)
        
        AuditService.log_event(
            db=db,
            event_type="organization_created",
            
            
            
            success=True,
            organization_id=org.id,
            user_id=owner_id
        )
        
        return org

    @staticmethod
    def remove_member(db: Session, org_id: uuid.UUID, member_id: uuid.UUID, actor_id: uuid.UUID):
        member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.id == member_id
        ).first()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
            
        if member.role == "owner":
            # Ensure there is at least one other owner before removing this one
            owner_count = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == "owner",
                OrganizationMember.id != member_id
            ).count()
            if owner_count == 0:
                raise HTTPException(status_code=400, detail="Cannot remove the last owner of the organization.")
                
        db.delete(member)
        db.commit()
        
        AuditService.log_event(
            db=db,
            event_type="member_removed",
            
            
            
            success=True,
            organization_id=org_id,
            user_id=actor_id,
            metadata={"removed_user_id": str(member.user_id)}
        )
