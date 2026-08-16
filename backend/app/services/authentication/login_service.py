import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.identity import LoginEvent
from app.services.authentication.session_service import SessionService
from app.services.authentication.authentication_policy import AuthenticationPolicy
from app.services.authorization.audit_service import AuditService

class LoginService:
    @staticmethod
    def record_login_attempt(db: Session, user_id: uuid.UUID, provider: str, success: bool, ip_hash: str = None, user_agent_hash: str = None, metadata: dict = None):
        event = LoginEvent(
            user_id=user_id,
            provider=provider,
            event_type="login",
            status="success" if success else "failed",
            ip_hash=ip_hash,
            user_agent_hash=user_agent_hash,
            metadata_payload=metadata or {}
        )
        db.add(event)
        db.commit()

        # Also push to audit service
        AuditService.log_event(
            db=db,
            event_type="login_success" if success else "login_failure",
            success=success,
            metadata={"provider": provider, **(metadata or {})},
            user_id=user_id
        )

    @staticmethod
    def enforce_sso_and_login(db: Session, user: User, provider: str, ip_hash: str = None, user_agent_hash: str = None):
        if not AuthenticationPolicy.enforce_policy_for_user(db, user.id, provider):
            # Record SSO blocked
            LoginService.record_login_attempt(db, user.id, provider, success=False, metadata={"reason": "sso_blocked_login"}, ip_hash=ip_hash, user_agent_hash=user_agent_hash)
            raise ValueError("SSO Policy enforcement blocked login via this provider")
            
        LoginService.record_login_attempt(db, user.id, provider, success=True, ip_hash=ip_hash, user_agent_hash=user_agent_hash)
        
        session_token, refresh_token, session = SessionService.create_session(db, user.id, ip_hash, user_agent_hash)
        return session_token, refresh_token, session
