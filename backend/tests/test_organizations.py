import uuid
from app.models.organization import Organization, OrganizationMember
from app.services.authorization.organization_service import OrganizationService

def test_create_organization(db_session, test_user):
    org = OrganizationService.create_organization(db_session, name="Test Org", slug="test-org", owner_id=test_user.id)
    assert org.id is not None
    assert org.name == "Test Org"
    assert org.slug == "test-org"
    assert org.owner_id == test_user.id
    
    # Check that owner is automatically a member
    member = db_session.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).first()
    assert member is not None
    assert member.user_id == test_user.id
    assert member.role == "owner"
