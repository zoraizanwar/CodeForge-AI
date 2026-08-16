"""
Pydantic API schemas for CodeForge AI Step 12 Multi-Agent Runs.
"""
import uuid
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AgentRunCreateSchema(BaseModel):
    task_description: str
    task_id: Optional[uuid.UUID] = None


class AgentRunStepResponseSchema(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    agent_type: str
    status: str
    input_context: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    job_id: Optional[uuid.UUID] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRunResponseSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    parent_job_id: Optional[uuid.UUID] = None
    status: str
    current_agent: Optional[str] = None
    workflow_stage: str
    overall_progress: int
    final_decision: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    steps: List[AgentRunStepResponseSchema] = []

    model_config = ConfigDict(from_attributes=True)
