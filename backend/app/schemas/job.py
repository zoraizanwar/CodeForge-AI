"""
Pydantic schemas for CodeForge AI Step 11 Job Orchestration & Real-Time Monitoring.
"""
import uuid
import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AgentJobCreateSchema(BaseModel):
    repository_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    job_type: str = Field(..., description="Job type: analysis, agent_task, execution, repair, pull_request")
    priority: int = 0
    payload: Optional[Dict[str, Any]] = None


class AgentJobResponseSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    job_type: str
    status: str
    progress: int
    current_stage: str
    attempt_count: int
    max_attempts: int
    priority: int
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class JobProgressUpdateSchema(BaseModel):
    job_id: uuid.UUID
    progress: int
    current_stage: str
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class JobCancelResponseSchema(BaseModel):
    job_id: uuid.UUID
    status: str
    message: str
