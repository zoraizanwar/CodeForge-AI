import uuid
import datetime
import secrets
import hashlib
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.identity import UserSession

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

class SessionService:
    @staticmethod
    def create_session(db: Session, user_id: uuid.UUID, ip_hash: str = None, user_agent_hash: str = None) -> Tuple[str, str, UserSession]:
        session_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        refresh_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        
        db_session = UserSession(
            user_id=user_id,
            token_hash=hash_token(session_token),
            refresh_token_hash=hash_token(refresh_token),
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            ip_hash=ip_hash,
            user_agent_hash=user_agent_hash
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        return session_token, refresh_token, db_session

    @staticmethod
    def revoke_session(db: Session, session_id: uuid.UUID) -> bool:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if not session or session.revoked_at:
            return False
        
        session.revoked_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        return True

    @staticmethod
    def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> None:
        db.query(UserSession).filter(
            UserSession.user_id == user_id, 
            UserSession.revoked_at.is_(None)
        ).update({"revoked_at": datetime.datetime.now(datetime.timezone.utc)}, synchronize_session=False)
        db.commit()
        
    @staticmethod
    def rotate_refresh_token(db: Session, refresh_token: str) -> Tuple[Optional[str], Optional[str], Optional[UserSession], bool]:
        hashed = hash_token(refresh_token)
        session = db.query(UserSession).filter(UserSession.refresh_token_hash == hashed).first()
        
        if not session:
            return None, None, None, False
            
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Check if already revoked (Refresh Reuse Detection)
        if session.revoked_at:
            # We would record a security event here
            return None, None, None, True
            
        if now > session.refresh_expires_at:
            return None, None, None, False
            
        # Rotate
        new_session_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)
        
        session.token_hash = hash_token(new_session_token)
        session.refresh_token_hash = hash_token(new_refresh_token)
        session.expires_at = now + datetime.timedelta(hours=24)
        session.refresh_expires_at = now + datetime.timedelta(days=30)
        session.last_used_at = now
        
        db.commit()
        db.refresh(session)
        
        return new_session_token, new_refresh_token, session, False
