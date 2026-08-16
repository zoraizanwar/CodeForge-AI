import uuid
import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RepositoryImport(BaseModel):
    """Schema for initiating repository imports."""
    github_repo_id: int = Field(..., description="The unique GitHub repository ID.")

class RepositoryResponse(BaseModel):
    """Schema for serializing repository connection profiles."""
    id: uuid.UUID
    github_repo_id: int
    name: str
    full_name: str
    owner: str
    default_branch: str
    status: str
    error_message: Optional[str] = None
    languages: Optional[Dict[str, float]] = None
    frameworks: Optional[List[str]] = None
    dependency_files: Optional[List[str]] = None
    last_indexed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class FileTreeItem(BaseModel):
    """Schema representing an individual file or directory node inside the repository tree."""
    name: str
    path: str
    type: str  # "file" or "directory"
    size: Optional[int] = None
    children: Optional[List['FileTreeItem']] = None

# Support self-referencing definitions for recursive tree structures
FileTreeItem.model_rebuild()

class FileContentResponse(BaseModel):
    """Schema representing file metadata and textual contents."""
    name: str
    path: str
    size: int
    content: str
