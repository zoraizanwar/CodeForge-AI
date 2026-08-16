"""
Pydantic schemas for AI Software Engineer Agent API, Execution, Git/PR, & Autonomous Feedback Repair Loop (Step 7, 8, 9, & 10).
"""
import uuid
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class TaskCreateRequest(BaseModel):
    task: str = Field(..., min_length=5, max_length=2000)

    @field_validator("task")
    @classmethod
    def task_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Task description cannot be blank.")
        return s


class ImplementationPlanSchema(BaseModel):
    task_summary: str = Field(default="")
    architecture_understanding: str = Field(default="")
    relevant_files: List[str] = Field(default_factory=list)
    relevant_symbols: List[str] = Field(default_factory=list)
    proposed_changes: List[str] = Field(default_factory=list)
    dependencies_affected: List[str] = Field(default_factory=list)
    tests: List[str] = Field(default_factory=list)
    implementation_order: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class FileChangeSchema(BaseModel):
    file_path: str
    operation: str = Field(..., description="create, modify, or delete")
    original_content: Optional[str] = None
    proposed_content: str = ""
    explanation: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    diff: str = ""


class CodeGenerationResponseSchema(BaseModel):
    changes: List[FileChangeSchema] = Field(default_factory=list)
    summary: str = Field(default="")


class AgentTaskResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    task_description: str
    status: str  # pending, analyzing, planning, generating, ready_for_review, approved, executing, execution_failed, repairing, repair_ready, execution_passed, pr_ready, pr_created, failed, human_review_required
    is_approved: bool = False
    approved_patch_hash: Optional[str] = None
    approved_at: Optional[datetime.datetime] = None
    plan: Optional[ImplementationPlanSchema] = None
    files_analyzed: Optional[List[str]] = None
    files_to_modify: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

    model_config = {"from_attributes": True}


class AgentTaskChangesResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    changes: List[FileChangeSchema]
    files_to_modify: List[str]


# ─── Execution Schemas (Step 8) ───────────────────────────────────────────

class CommandResultSchema(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float = 0.0


class TestSummarySchema(BaseModel):
    passed: bool
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    duration_seconds: float = 0.0
    commands: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)


class AgentExecutionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    status: str  # pending, preparing, applying, testing, passed, failed, cancelled
    workspace_path: str
    command_results: Optional[List[CommandResultSchema]] = None
    test_summary: Optional[TestSummarySchema] = None
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# ─── Git & PR Schemas (Step 9) ────────────────────────────────────────────

class GitOperationResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    task_id: uuid.UUID
    execution_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    operation_type: str  # branch, commit, push, pull_request
    status: str  # pending, preparing, applying, committing, pushing, creating_pr, completed, failed, cancelled
    branch_name: str
    commit_sha: Optional[str] = None
    remote_branch: Optional[str] = None
    pull_request_number: Optional[int] = None
    pull_request_url: Optional[str] = None
    commit_message: Optional[str] = None
    error_message: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# ─── Feedback Loop & Repair Schemas (Step 10) ──────────────────────────────

class RootCauseAnalysisSchema(BaseModel):
    failure_category: str
    root_cause: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    affected_files: List[str] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    recommended_fix: str = ""
    requires_dependency_change: bool = False


class AgentIterationResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    iteration_number: int
    trigger_execution_id: Optional[uuid.UUID] = None
    status: str  # analyzing, planning, generating, validating, executing, passed, failed, stopped
    failure_category: Optional[str] = None
    failure_summary: Optional[str] = None
    root_cause: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    patch_hash: Optional[str] = None
    execution_id: Optional[uuid.UUID] = None
    files_changed: Optional[List[FileChangeSchema]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
