"""
Pydantic schemas for Audit Events & Operational Metrics API endpoints (Step 14).
"""
import uuid
import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class AuditEventResponseSchema(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    repository_id: Optional[uuid.UUID] = None
    agent_task_id: Optional[uuid.UUID] = None
    agent_run_id: Optional[uuid.UUID] = None
    job_id: Optional[uuid.UUID] = None
    event_type: str
    severity: str
    request_id: Optional[str] = None
    success: bool
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AuditEventListResponseSchema(BaseModel):
    total: int
    items: List[AuditEventResponseSchema]
    limit: int
    offset: int


class SystemStatsResponseSchema(BaseModel):
    timestamp: datetime.datetime
    metrics: Dict[str, Any]
    user_stats: Dict[str, Any]
