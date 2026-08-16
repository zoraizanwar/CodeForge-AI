import secrets
import hashlib
import datetime
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db


from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.github import GitHubInstallation, OAuthState
from app.services.github import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter()

def get_github_service() -> GitHubService:
    """Dependency resolver for GitHubService. Fails if config variables are missing."""
    try:
        return GitHubService()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub service configuration error: {str(e)}"
        )

@router.get("/connect", response_model=Dict[str, str])
def connect_github(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates a secure cryptographically random state token, stores its SHA-256 hash
    in the database, and returns the GitHub App authorization installation URL.
    """
    # Create secure state token
    state_token = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state_token.encode("utf-8")).hexdigest()
    
    # Expiration: 10 minutes from now
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    
    # Store hashed representation to database
    oauth_state = OAuthState(
        user_id=current_user.id,
        state_hash=state_hash,
        expires_at=expires_at
    )
    db.add(oauth_state)
    db.commit()
    
    # Reconstruct App installation URL
    app_url = f"https://github.com/apps/{settings.GITHUB_APP_NAME}/installations/new?state={state_token}"
    return {"url": app_url}

class SyncInstallationRequest(BaseModel):
    installation_id: Optional[int] = None

@router.get("/callback")
async def github_callback(
    installation_id: int = Query(...),
    state: Optional[str] = Query(None),
    setup_action: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    github_service: GitHubService = Depends(get_github_service)
):
    """
    Receives authorization callback redirection from GitHub, validates state token
    or matches existing installation, authenticates installation metadata, and links
    it to the CodeForge user.
    """
    user_id = None
    if state:
        state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
        state_record = db.query(OAuthState).filter(OAuthState.state_hash == state_hash).first()
        if not state_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter."
            )
        if state_record.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State has already been used."
            )
        now = datetime.datetime.now(datetime.timezone.utc)
        if state_record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State has expired."
            )
        state_record.used_at = now
        user_id = state_record.user_id
        db.commit()
    else:
        existing_inst = db.query(GitHubInstallation).filter(
            GitHubInstallation.installation_id == installation_id
        ).first()
        if existing_inst:
            user_id = existing_inst.user_id

        if not user_id:
            recent_state = db.query(OAuthState).filter(
                OAuthState.used_at.is_(None),
                OAuthState.expires_at > datetime.datetime.now(datetime.timezone.utc)
            ).order_by(OAuthState.created_at.desc()).first()
            if recent_state:
                recent_state.used_at = datetime.datetime.now(datetime.timezone.utc)
                user_id = recent_state.user_id
                db.commit()

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to associate GitHub installation with a CodeForge user. Initiate connection from CodeForge."
        )


    try:
        details = await github_service.get_installation_details(installation_id)
    except Exception as e:
        logger.error("Failed to verify GitHub installation callback details: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to retrieve installation details: {str(e)}"
        )

    account = details.get("account", {})
    github_account_id = account.get("id")
    github_account_login = account.get("login")
    github_account_type = account.get("type")

    if not github_account_id or not github_account_login or not github_account_type:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid installation metadata returned from GitHub."
        )

    # Check for linking conflict with another user
    existing = db.query(GitHubInstallation).filter(
        GitHubInstallation.installation_id == installation_id
    ).first()
    if existing and existing.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This GitHub installation is already linked to another CodeForge account."
        )

    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.user_id == user_id
    ).first()

    if not installation:
        installation = GitHubInstallation(user_id=user_id)
        db.add(installation)


    installation.installation_id = installation_id
    installation.github_account_id = github_account_id
    installation.github_account_login = github_account_login
    installation.github_account_type = github_account_type
    installation.updated_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()

    frontend_url = settings.FRONTEND_URL or (settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:5174")
    return RedirectResponse(url=f"{frontend_url}/?github=connected")

@router.post("/sync", response_model=Dict[str, Any])
async def sync_github_installation(
    payload: Optional[SyncInstallationRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    github_service: GitHubService = Depends(get_github_service)
):
    """
    Syncs or links an existing GitHub installation ID for the authenticated user.
    """
    inst_id = payload.installation_id if payload else None

    if not inst_id:
        existing = db.query(GitHubInstallation).filter(GitHubInstallation.user_id == current_user.id).first()
        if existing:
            inst_id = existing.installation_id

    details = None
    if inst_id:
        try:
            details = await github_service.get_installation_details(inst_id)
        except Exception as e:
            logger.warning(f"Could not fetch installation details for inst_id {inst_id}: {str(e)}")
            details = None

    if not details:
        try:
            installations = await github_service.list_app_installations()
            if installations:
                # Find most recent installation
                details = installations[-1]
                inst_id = details.get("id")
        except Exception as e:
            logger.error(f"Failed to list GitHub App installations: {str(e)}")

    if not details or not inst_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active GitHub App installation found on GitHub. Please click 'Connect GitHub' to authorize/install CodeForge AI on your GitHub account."
        )


    account = details.get("account", {})
    github_account_id = account.get("id")
    github_account_login = account.get("login")
    github_account_type = account.get("type")

    if not github_account_id or not github_account_login:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid installation metadata returned from GitHub."
        )

    existing = db.query(GitHubInstallation).filter(GitHubInstallation.installation_id == inst_id).first()
    if existing and existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This GitHub installation is already linked to another CodeForge account."
        )

    installation = db.query(GitHubInstallation).filter(GitHubInstallation.user_id == current_user.id).first()

    if not installation:
        installation = GitHubInstallation(user_id=current_user.id)
        db.add(installation)

    installation.installation_id = inst_id
    installation.github_account_id = github_account_id
    installation.github_account_login = github_account_login
    installation.github_account_type = github_account_type
    installation.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    return {
        "connected": True,
        "github_login": github_account_login,
        "github_account_type": github_account_type,
        "installation_id": inst_id
    }



@router.get("/status", response_model=Dict[str, Any])
def get_github_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns connection status and profile details of the connected GitHub account.
    """
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        return {"connected": False}
        
    return {
        "connected": True,
        "github_login": installation.github_account_login,
        "github_account_type": installation.github_account_type
    }

@router.get("/repositories", response_model=Dict[str, Any])
async def get_github_repositories(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    github_service: GitHubService = Depends(get_github_service)
):
    """
    Fetches the list of repositories accessible to the GitHub App installation.
    Returns safe, redacted metadata containing no access tokens or keys.
    """
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub account not connected."
        )
        
    try:
        raw_repos_data = await github_service.list_repositories(
            installation_id=installation.installation_id,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error("Failed to query repositories from GitHub: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API integration error: {str(e)}"
        )
        
    # Standardize output to safe, redacted repository metadata list
    safe_repos = []
    raw_list = raw_repos_data.get("repositories", []) if isinstance(raw_repos_data, dict) else (raw_repos_data if isinstance(raw_repos_data, list) else [])
    for r in raw_list:
        owner_info = r.get("owner", {})
        if isinstance(owner_info, str):
            owner_obj = {"id": 0, "login": owner_info, "type": "User", "avatar_url": ""}
        elif isinstance(owner_info, dict):
            owner_obj = {
                "id": owner_info.get("id", 0),
                "login": owner_info.get("login", ""),
                "type": owner_info.get("type", "User"),
                "avatar_url": owner_info.get("avatar_url", "")
            }
        else:
            owner_obj = {"id": 0, "login": "", "type": "User", "avatar_url": ""}

        safe_repos.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "private": r.get("private", False),
            "html_url": r.get("html_url"),
            "default_branch": r.get("default_branch", "main"),
            "owner": owner_obj
        })

    total_count = raw_repos_data.get("total_count", len(safe_repos)) if isinstance(raw_repos_data, dict) else len(safe_repos)

    return {
        "total_count": total_count,
        "repositories": safe_repos
    }


@router.delete("/disconnect", response_model=Dict[str, Any])
def disconnect_github(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes the GitHub installation relationship for the authenticated User.
    """
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub account not connected."
        )
        
    db.delete(installation)
    db.commit()
    
    return {
        "status": "ok",
        "message": "GitHub connection removed successfully."
    }
