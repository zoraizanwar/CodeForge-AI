import os
import logging
import uuid
import shutil
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.services.authorization.permission_service import PermissionService

from app.core.database import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.github import GitHubInstallation
from app.models.repository import Repository
from app.schemas.repository import RepositoryImport, RepositoryResponse, FileTreeItem, FileContentResponse
from app.services.repository import (
    RepositoryService,
    get_safe_workspace_path,
    should_exclude_file,
    is_binary_file,
    EXCLUDED_FOLDERS
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[RepositoryResponse])
def list_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all repositories imported by the authenticated CodeForge User."""
    repositories = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    return repositories

@router.post("/import", response_model=RepositoryResponse, status_code=status.HTTP_202_ACCEPTED)
def import_repository(
    payload: RepositoryImport,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiates background importing/indexing for a specified GitHub repository ID.
    Validates permissions and updates database statuses before queuing.
    """
    # 1. Fetch GitHub App installation for the user
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App connection is not active. Connect GitHub App first."
        )
        
    # Check if this repository is already imported
    repo = db.query(Repository).filter(
        Repository.user_id == current_user.id,
        Repository.github_repo_id == payload.github_repo_id
    ).first()
    
    if repo:
        # If already importing, don't trigger duplicate tasks
        if repo.status == "importing":
            return repo
        # Re-importing resets status
        repo.status = "importing"
        repo.error_message = None
        db.commit()
    else:
        # Create new Repository record
        local_path = RepositoryService.get_repository_workspace(
            user_id=current_user.id,
            github_repo_id=payload.github_repo_id
        )
        repo = Repository(
            user_id=current_user.id,
            github_repo_id=payload.github_repo_id,
            name=f"repo-{payload.github_repo_id}",  # Placeholders, background task overwrites
            full_name=f"pending/repo-{payload.github_repo_id}",
            owner="pending",
            default_branch="main",
            local_path=local_path,
            status="importing"
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        
    # Queue extraction and walk parsing as a background task
    background_tasks.add_task(
        RepositoryService.import_repository_task,
        repo.id,
        installation.installation_id,
        db
    )
    
    return repo

@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves status details for a connected repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo:
        PermissionService.require_repository_read_access(db, current_user.id, repo)
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
        
    return repo

@router.delete("/{repo_id}", response_model=Dict[str, str])
def delete_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes the repository record and removes its local disk workspace safely.
    Validates path containment prior to execution.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo:
        PermissionService.require_repository_read_access(db, current_user.id, repo)
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
        
    try:
        # Resolve and validate path boundary
        safe_path = get_safe_workspace_path(repo.local_path)
        workspace_root = os.path.realpath(settings.workspace_root_resolved)
        
        # Double check containment boundary inside workspaces root folder
        if not safe_path.startswith(workspace_root + os.sep) and safe_path != workspace_root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security breach: Cannot delete directories outside the workspace root."
            )
            
        # Clean local folder
        if os.path.exists(safe_path):
            shutil.rmtree(safe_path)
            
    except Exception as e:
        logger.error("Failed to delete workspace folder: %s", str(e))
        # Keep deletion going to clear database even if disk cleanups fail
        
    db.delete(repo)
    db.commit()
    
    return {"status": "ok", "message": "Repository removed successfully."}

@router.get("/{repo_id}/tree", response_model=List[FileTreeItem])
def get_repository_tree(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Traverses repository workspace directory structure and returns a hierarchical file tree list.
    Fails if the index status is not set to indexed.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo:
        PermissionService.require_repository_read_access(db, current_user.id, repo)
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
        
    if repo.status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository workspace has not completed indexing."
        )
        
    # Boundary-checked walking builder
    def build_tree_nodes(base_dir: str, sub_dir: str = "") -> List[FileTreeItem]:
        safe_dir = get_safe_workspace_path(base_dir, sub_dir)
        nodes = []
        try:
            for entry in os.scandir(safe_dir):
                # Ignore control directories in walk
                if entry.is_dir():
                    if entry.name in EXCLUDED_FOLDERS:
                        continue
                    rel_path = f"{sub_dir}/{entry.name}" if sub_dir else entry.name
                    # Trigger traversal verification
                    get_safe_workspace_path(base_dir, rel_path)
                    
                    children = build_tree_nodes(base_dir, rel_path)
                    nodes.append(FileTreeItem(
                        name=entry.name,
                        path=rel_path,
                        type="directory",
                        children=children
                    ))
                else:
                    if should_exclude_file(entry.name):
                        continue
                    # Ignore files exceeding size limit
                    size = entry.stat().st_size
                    if size > 1024 * 1024:  # 1MB limit
                        continue
                    rel_path = f"{sub_dir}/{entry.name}" if sub_dir else entry.name
                    get_safe_workspace_path(base_dir, rel_path)
                    
                    # Ignore binary file types
                    if is_binary_file(entry.path):
                        continue
                        
                    nodes.append(FileTreeItem(
                        name=entry.name,
                        path=rel_path,
                        type="file",
                        size=size
                    ))
        except Exception:
            pass
            
        # Sort node outcomes (Directories first, then Files)
        nodes.sort(key=lambda n: (0 if n.type == "directory" else 1, n.name.lower()))
        return nodes

    return build_tree_nodes(repo.local_path)

@router.get("/{repo_id}/file", response_model=FileContentResponse)
def read_repository_file(
    repo_id: uuid.UUID,
    path: str = Query(..., description="Relative file path inside workspace."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves safe code file content from the workspace boundary.
    Enforces maximum sizes and rejects secret config patterns.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo:
        PermissionService.require_repository_read_access(db, current_user.id, repo)
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
        
    if repo.status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository workspace has not completed indexing."
        )
        
    try:
        # Strict validation checks
        safe_file_path = get_safe_workspace_path(repo.local_path, path)
        
        # Verify file type
        if os.path.isdir(safe_file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested path is a directory, not a file."
            )
            
        # Reject access to sensitive names
        file_name = os.path.basename(safe_file_path)
        if should_exclude_file(file_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this sensitive file is forbidden."
            )
            
        # Enforce size restrictions
        size = os.path.getsize(safe_file_path)
        if size > 1024 * 1024:  # 1MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds maximum read limit of 1MB."
            )
            
        # Reject binary files
        if is_binary_file(safe_file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot read binary file contents."
            )
            
        # Fetch file data contents
        with open(safe_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        return FileContentResponse(
            name=file_name,
            path=path,
            size=size,
            content=content
        )
        
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found inside workspace."
        )
    except Exception as e:
        logger.error("Failed to read file: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing file read."
        )

@router.post("/{repo_id}/index", response_model=RepositoryResponse, status_code=status.HTTP_202_ACCEPTED)
def reindex_repository(
    repo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually triggers background re-indexing for an active repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo:
        PermissionService.require_repository_read_access(db, current_user.id, repo)
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )
        
    # Get active install
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App connection is not active."
        )
        
    repo.status = "importing"
    repo.error_message = None
    db.commit()
    
    background_tasks.add_task(
        RepositoryService.import_repository_task,
        repo.id,
        installation.installation_id,
        db
    )
    
    return repo
