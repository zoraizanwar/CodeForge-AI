import logging
import jwt
import uuid
import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.schemas.user import UserCreate, UserLogin, Token, UserResponse
from app.services.auth import (
    get_user_by_email,
    get_user_by_id,
    register_user,
    authenticate_user,
    create_access_token
)
from app.models.user import User
from app.models.identity import UserSession, ExternalIdentity
from app.services.authentication.login_service import LoginService
from app.services.authentication.session_service import SessionService
from app.services.authentication.identity_service import IdentityService
from app.services.authentication.oauth_service import OAuthService
from app.services.authentication.authentication_policy import AuthenticationPolicy
from app.services.authorization.audit_service import AuditService

logger = logging.getLogger("codeforge.auth")
router = APIRouter()

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
        
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user profile"
        )
        
    return user

def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def get_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "unknown")

# Schemas
class RefreshRequest(BaseModel):
    refresh_token: str

class OAuthState(BaseModel):
    state: str
    provider: str

class IdentityResponse(BaseModel):
    id: uuid.UUID
    provider: str
    provider_subject: str
    provider_email: Optional[str]
    provider_username: Optional[str]
    created_at: str

    class Config:
        orm_mode = True

class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: str
    expires_at: str
    last_used_at: Optional[str]

    class Config:
        orm_mode = True

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email address already registered.")
        
    try:
        new_user = register_user(db, email=user_in.email, password=user_in.password)
        return new_user
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to register user.")

@router.post("/login")
async def login(request: Request, credentials_in: UserLogin, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    ua = get_user_agent(request)

    user = authenticate_user(db, email=credentials_in.email, password=credentials_in.password)
    if not user or not user.is_active:
        # Enforce account enumeration protection
        # We record generic failure
        if user:
            LoginService.record_login_attempt(db, user.id, "password", False, ip, ua)
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    try:
        session_token, refresh_token, session = LoginService.enforce_sso_and_login(db, user, "password", ip, ua)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Keep compatibility with existing JWT for now
    jwt_token = create_access_token(user.id)
    
    return {
        "access_token": jwt_token, 
        "token_type": "bearer",
        "session_token": session_token,
        "refresh_token": refresh_token
    }

@router.post("/refresh")
async def refresh_session(request: Request, req: RefreshRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    
    new_session_token, new_refresh_token, session, reuse_detected = SessionService.rotate_refresh_token(db, req.refresh_token)
    
    if reuse_detected:
        AuditService.log_event(
            db=db,
            event_type="refresh_reuse_detected",
            success=False,
            metadata={"ip": ip, "user_agent": ua}
        )
        raise HTTPException(status_code=401, detail="Session invalid")
        
    if not session:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    jwt_token = create_access_token(session.user_id)
    
    AuditService.log_event(
        db=db,
        event_type="refresh_rotated",
        success=True,
        metadata={"session_id": str(session.id)},
        user_id=session.user_id
    )

    return {
        "access_token": jwt_token, 
        "token_type": "bearer",
        "session_token": new_session_token,
        "refresh_token": new_refresh_token
    }

@router.post("/logout")
async def logout(request: Request, req: RefreshRequest, db: Session = Depends(get_db)):
    import hashlib
    hashed = hashlib.sha256(req.refresh_token.encode("utf-8")).hexdigest()
    session = db.query(UserSession).filter(UserSession.refresh_token_hash == hashed).first()
    if session:
        SessionService.revoke_session(db, session.id)
        AuditService.log_event(
            db=db, event_type="logout", success=True, metadata={"session_id": str(session.id)}, user_id=session.user_id
        )
    return {"detail": "Logged out"}

@router.post("/logout-all")
async def logout_all(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    SessionService.revoke_all_sessions(db, current_user.id)
    AuditService.log_event(db=db, event_type="logout_all", success=True, metadata={}, user_id=current_user.id)
    return {"detail": "Logged out of all sessions"}

@router.get("/sessions")
async def get_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.revoked_at.is_(None)
    ).all()
    return [{"id": s.id, "created_at": s.created_at, "expires_at": s.expires_at, "last_used_at": s.last_used_at} for s in sessions]

@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(UserSession).filter(UserSession.id == session_id, UserSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    SessionService.revoke_session(db, session.id)
    AuditService.log_event(db=db, event_type="session_revoked", success=True, metadata={"session_id": str(session_id)}, user_id=current_user.id)
    return {"detail": "Session revoked"}

@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: str, redirect_uri: str):
    if provider != "github":
        raise HTTPException(status_code=400, detail="Unsupported provider")
    state = secrets.token_urlsafe(32)
    url = OAuthService.get_github_authorize_url(state, redirect_uri)
    return {"url": url, "state": state}

@router.post("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: str, state: str, original_state: str, redirect_uri: str, db: Session = Depends(get_db)):
    if provider != "github":
        raise HTTPException(status_code=400, detail="Unsupported provider")
    
    if state != original_state:
        raise HTTPException(status_code=400, detail="State mismatch")

    ip = get_client_ip(request)
    ua = get_user_agent(request)
    
    try:
        access_token = await OAuthService.exchange_github_code(code, redirect_uri)
        gh_user = await OAuthService.get_github_user(access_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail="OAuth failed")

    provider_subject = str(gh_user["id"])
    provider_email = gh_user.get("email")
    provider_username = gh_user.get("login")

    # Find external identity
    identity = IdentityService.get_identity_by_provider(db, provider, provider_subject)
    user = None
    if identity:
        user = get_user_by_id(db, identity.user_id)
    else:
        # Check if email exists
        if provider_email:
            user = get_user_by_email(db, provider_email)
            if user:
                # Link safe if email verified. (Assuming verified in this context, or we enforce explicit link)
                identity = IdentityService.link_external_identity(db, user.id, provider, provider_subject, provider_email, provider_username, gh_user)
            else:
                # Create user
                from app.services.auth import get_password_hash
                random_pass = get_password_hash(secrets.token_urlsafe(32))
                user = User(email=provider_email, hashed_password=random_pass, is_active=True)
                db.add(user)
                db.commit()
                db.refresh(user)
                identity = IdentityService.link_external_identity(db, user.id, provider, provider_subject, provider_email, provider_username, gh_user)
        else:
            raise HTTPException(status_code=400, detail="Email required from provider")

    try:
        session_token, refresh_token, session = LoginService.enforce_sso_and_login(db, user, provider, ip, ua)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    jwt_token = create_access_token(user.id)
    
    return {
        "access_token": jwt_token, 
        "token_type": "bearer",
        "session_token": session_token,
        "refresh_token": refresh_token
    }

@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/identities")
async def get_identities(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    idents = IdentityService.get_user_identities(db, current_user.id)
    return [{"id": str(i.id), "provider": i.provider, "provider_subject": i.provider_subject, "provider_email": i.provider_email, "provider_username": i.provider_username, "created_at": str(i.created_at)} for i in idents]

@router.delete("/identities/{identity_id}")
async def unlink_identity(identity_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = IdentityService.unlink_external_identity(db, current_user.id, identity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {"detail": "Identity unlinked"}
