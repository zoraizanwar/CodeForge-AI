import pytest
from app.models.identity import ExternalIdentity, UserSession, LoginEvent, OrganizationIdentityPolicy
from app.services.authentication.session_service import SessionService
from app.services.authentication.identity_service import IdentityService
from app.services.authentication.authentication_policy import AuthenticationPolicy
from app.models.organization import Organization, OrganizationMember

def test_session_creation(db_session, test_user):
    session_token, refresh_token, session = SessionService.create_session(db_session, test_user.id)
    assert session_token is not None
    assert refresh_token is not None
    assert session.user_id == test_user.id

def test_refresh_rotation(db_session, test_user):
    _, refresh_token, session = SessionService.create_session(db_session, test_user.id)
    
    new_s, new_r, new_session, reuse = SessionService.rotate_refresh_token(db_session, refresh_token)
    assert reuse is False
    assert new_s is not None
    assert new_r is not None
    assert new_session.id == session.id

def test_refresh_reuse_detection(db_session, test_user):
    _, refresh_token, session = SessionService.create_session(db_session, test_user.id)
    SessionService.revoke_session(db_session, session.id)
    
    new_s, new_r, new_session, reuse = SessionService.rotate_refresh_token(db_session, refresh_token)
    assert reuse is True
    assert new_session is None

def test_identity_linking(db_session, test_user):
    identity = IdentityService.link_external_identity(
        db_session, test_user.id, "github", "123", "test@test.com", "testuser", {}
    )
    assert identity.provider == "github"
    assert identity.provider_subject == "123"

def test_sso_policy_enforcement(db_session, test_user):
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    
    member = OrganizationMember(organization_id=org.id, user_id=test_user.id, role="owner")
    db_session.add(member)
    db_session.commit()
    
    policy = AuthenticationPolicy.get_policy(db_session, org.id)
    policy.require_sso = True
    policy.allow_password_login = False
    policy.allowed_providers = ["github"]
    db_session.commit()
    
    # Enforce password should fail
    assert AuthenticationPolicy.enforce_policy_for_user(db_session, test_user.id, "password") is False
    # Enforce github should pass
    assert AuthenticationPolicy.enforce_policy_for_user(db_session, test_user.id, "github") is True
