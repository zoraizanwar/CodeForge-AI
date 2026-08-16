import uuid
from sqlalchemy.orm import Session
from app.models.identity import OrganizationIdentityPolicy
from app.models.organization import OrganizationMember

class AuthenticationPolicy:
    @staticmethod
    def get_policy(db: Session, organization_id: uuid.UUID) -> OrganizationIdentityPolicy:
        policy = db.query(OrganizationIdentityPolicy).filter(
            OrganizationIdentityPolicy.organization_id == organization_id
        ).first()
        
        if not policy:
            policy = OrganizationIdentityPolicy(organization_id=organization_id)
            db.add(policy)
            db.commit()
            db.refresh(policy)
            
        return policy

    @staticmethod
    def enforce_policy_for_user(db: Session, user_id: uuid.UUID, provider: str = "password") -> bool:
        """
        Enforce organization identity policies for a user.
        If any organization the user belongs to has require_sso=True, password login might be disabled
        unless the provider matches the allowed providers.
        """
        memberships = db.query(OrganizationMember).filter(OrganizationMember.user_id == user_id).all()
        for membership in memberships:
            policy = AuthenticationPolicy.get_policy(db, membership.organization_id)
            
            if provider == "password" and policy.require_sso and not policy.allow_password_login:
                return False
                
            if provider != "password" and policy.require_sso and policy.allowed_providers:
                if provider not in policy.allowed_providers:
                    return False
        return True
