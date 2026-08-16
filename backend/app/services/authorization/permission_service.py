import uuid
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.organization import OrganizationMember, Organization
from app.models.repository import Repository
from app.models.permission import RepositoryPermission

ROLE_HIERARCHY = {
    "owner": 50,
    "admin": 40,
    "developer": 30,
    "reviewer": 20,
    "viewer": 10,
}

REPO_ROLE_HIERARCHY = {
    "admin": 40,
    "write": 30,
    "review": 20,
    "read": 10,
}

class PermissionService:
    @staticmethod
    def _get_org_role_level(role: Optional[str]) -> int:
        if not role:
            return 0
        return ROLE_HIERARCHY.get(role.lower(), 0)
        
    @staticmethod
    def _get_repo_role_level(role: Optional[str]) -> int:
        if not role:
            return 0
        return REPO_ROLE_HIERARCHY.get(role.lower(), 0)

    @classmethod
    def get_organization_member(cls, db: Session, user_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[OrganizationMember]:
        return db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == "active"
        ).first()

    @classmethod
    def require_organization_role(cls, db: Session, user_id: uuid.UUID, organization_id: uuid.UUID, required_role: str) -> OrganizationMember:
        """Enforces that the user has at least the required role in the organization."""
        member = cls.get_organization_member(db, user_id, organization_id)
        if not member:
            raise HTTPException(status_code=403, detail="Not an active member of this organization.")
            
        member_level = cls._get_org_role_level(member.role)
        required_level = cls._get_org_role_level(required_role)
        
        if member_level < required_level:
            raise HTTPException(status_code=403, detail=f"Insufficient permissions. Required role: {required_role}")
            
        return member

    @classmethod
    def get_repository_access_level(cls, db: Session, user_id: uuid.UUID, repository: Repository) -> int:
        """
        Determines the effective repository access level for a user.
        Owner of the repository (if not org-owned) has admin.
        If org-owned, checks explicit repo permission first, then falls back to org role.
        """
        if repository.user_id == user_id and not repository.organization_id:
            return REPO_ROLE_HIERARCHY["admin"]

        if repository.organization_id:
            # 1. Check explicit repository permission for user
            repo_perm = db.query(RepositoryPermission).filter(
                RepositoryPermission.repository_id == repository.id,
                RepositoryPermission.user_id == user_id
            ).first()
            
            if repo_perm:
                return cls._get_repo_role_level(repo_perm.role)
                
            # 2. Check organization role
            member = cls.get_organization_member(db, user_id, repository.organization_id)
            if member:
                # Map org roles to repo roles conceptually
                org_level = cls._get_org_role_level(member.role)
                if org_level >= ROLE_HIERARCHY["admin"]:
                    return REPO_ROLE_HIERARCHY["admin"]
                elif org_level >= ROLE_HIERARCHY["developer"]:
                    return REPO_ROLE_HIERARCHY["write"]
                elif org_level >= ROLE_HIERARCHY["reviewer"]:
                    return REPO_ROLE_HIERARCHY["review"]
                elif org_level >= ROLE_HIERARCHY["viewer"]:
                    return REPO_ROLE_HIERARCHY["read"]
                    
        return 0

    @classmethod
    def require_repository_permission(cls, db: Session, user_id: uuid.UUID, repository: Repository, required_role: str):
        """Enforces that the user has at least the required role on the repository."""
        actual_level = cls.get_repository_access_level(db, user_id, repository)
        required_level = cls._get_repo_role_level(required_role)
        
        if actual_level == 0:
            raise HTTPException(status_code=404, detail="Repository not found.") # Hide existence
            
        if actual_level < required_level:
            raise HTTPException(status_code=403, detail=f"Insufficient repository permissions. Required: {required_role}")

    @classmethod
    def require_repository_write_access(cls, db: Session, user_id: uuid.UUID, repository: Repository):
        cls.require_repository_permission(db, user_id, repository, "write")

    @classmethod
    def require_repository_review_access(cls, db: Session, user_id: uuid.UUID, repository: Repository):
        cls.require_repository_permission(db, user_id, repository, "review")

    @classmethod
    def require_repository_read_access(cls, db: Session, user_id: uuid.UUID, repository: Repository):
        cls.require_repository_permission(db, user_id, repository, "read")
