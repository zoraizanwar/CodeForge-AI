"""Pydantic schemas for repository intelligence API (Step 6)."""
import uuid
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class SymbolResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    file_path: str
    line_number: int
    end_line_number: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class AnalysisStatusResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    status: str  # pending | processing | completed | failed
    architecture_summary: Optional[str] = None
    entry_points: Optional[List[str]] = None
    dependencies_parsed: Optional[Dict[str, str]] = None
    frameworks: Optional[List[str]] = None
    last_analyzed_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class DependenciesResponse(BaseModel):
    repository_id: uuid.UUID
    dependencies: Dict[str, str]
    frameworks: List[str]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Search query cannot be blank")
        return v.strip()


class SearchResultItem(BaseModel):
    chunk_id: uuid.UUID
    file_path: str
    language: str
    start_line: int
    end_line: int
    content: str
    symbol_name: Optional[str] = None
    score: Optional[float] = None  # cosine similarity distance (lower = more similar)


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int
