import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.services.authorization.organization_service import OrganizationService
from app.services.authorization.invitation_service import InvitationService
from app.services.authorization.permission_service import PermissionService

router = APIRouter()

class OrganizationCreate(BaseModel):
    name: str
    slug: str

class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    owner_id: uuid.UUID
    status: str
    
    class Config:
        from_attributes = True

class InviteRequest(BaseModel):
    email: EmailStr
    role: str

@router.post("", response_model=OrganizationResponse)
def create_organization(
    org_in: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    org = OrganizationService.create_organization(db, org_in.name, org_in.slug, current_user.id)
    return org

@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    members = db.query(OrganizationMember).filter(OrganizationMember.user_id == current_user.id, OrganizationMember.status == "active").all()
    org_ids = [m.organization_id for m in members]
    orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all()
    return orgs

@router.post("/{org_id}/invitations")
def invite_member(
    org_id: uuid.UUID,
    invite_in: InviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    token = InvitationService.invite_member(db, org_id, invite_in.email, invite_in.role, current_user.id)
    return {"message": "Invitation sent", "token": token} # Token returned for testing/development

@router.post("/invitations/{token}/accept")
def accept_invitation(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    InvitationService.accept_invitation(db, token, current_user.id, current_user.email)
    return {"message": "Invitation accepted"}

@router.delete("/{org_id}/members/{member_id}")
def remove_member(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    OrganizationService.remove_member(db, org_id, member_id, current_user.id)
    return {"message": "Member removed"}
