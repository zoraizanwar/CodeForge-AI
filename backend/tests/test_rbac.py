import uuid
import pytest
from app.services.authorization.permission_service import PermissionService, ROLE_HIERARCHY, REPO_ROLE_HIERARCHY
from app.models.repository import Repository
from app.models.organization import OrganizationMember, Organization
from app.models.permission import RepositoryPermission
from fastapi import HTTPException

def test_role_hierarchy():
    assert PermissionService._get_org_role_level("owner") > PermissionService._get_org_role_level("admin")
    assert PermissionService._get_org_role_level("admin") > PermissionService._get_org_role_level("developer")

def test_repo_role_hierarchy():
    assert PermissionService._get_repo_role_level("admin") > PermissionService._get_repo_role_level("write")
    assert PermissionService._get_repo_role_level("write") > PermissionService._get_repo_role_level("review")

def test_require_organization_role_success(db_session, test_user):
    org = Organization(name="Test Org", slug="test-org", owner_id=test_user.id)
    db_session.add(org)
    db_session.flush()
    
    member = OrganizationMember(organization_id=org.id, user_id=test_user.id, role="admin", status="active")
    db_session.add(member)
    db_session.commit()
    
    # Should not raise
    ret_member = PermissionService.require_organization_role(db_session, test_user.id, org.id, "developer")
    assert ret_member.role == "admin"

def test_require_organization_role_failure(db_session, test_user):
    org = Organization(name="Test Org", slug="test-org", owner_id=test_user.id)
    db_session.add(org)
    db_session.flush()
    
    member = OrganizationMember(organization_id=org.id, user_id=test_user.id, role="viewer", status="active")
    db_session.add(member)
    db_session.commit()
    
    with pytest.raises(HTTPException) as exc:
        PermissionService.require_organization_role(db_session, test_user.id, org.id, "developer")
    assert exc.value.status_code == 403
