"""
Pydantic schemas for CodeForge AI Step 12 Multi-Agent Software Engineering Workflow.
Enforces strict structured inputs and outputs across all specialized agents.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PlanItem(BaseModel):
    file_path: str
    action: str  # create, modify, delete
    description: str


class PlanResult(BaseModel):
    strategy: str
    affected_files: List[str]
    proposed_changes: List[PlanItem]
    risks: List[str]
    required_tests: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)


class FileOperation(BaseModel):
    file_path: str
    action: str  # create, modify, delete
    content: Optional[str] = None
    patch_diff: Optional[str] = None


class CodeGenerationResult(BaseModel):
    file_operations: List[FileOperation]
    summary: str
    total_files_changed: int
    total_size_bytes: int
    confidence: float = Field(..., ge=0.0, le=1.0)


class ReviewFinding(BaseModel):
    file: str
    line: int = 1
    category: str  # correctness, maintainability, architecture, regression, security, testing, suspicious
    severity: str  # critical, high, medium, low, info
    description: str
    recommendation: str


class ReviewResult(BaseModel):
    findings: List[ReviewFinding]
    approved: bool
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class SecurityFinding(BaseModel):
    rule_id: str
    severity: str  # critical, high, medium, low
    category: str  # path_traversal, auth, tenant_isolation, secret_exposure, command_injection, ssrf, sqli, xss, sensitive_file, git_credentials, protected_branch, dependency
    file: Optional[str] = None
    line: Optional[int] = None
    description: str
    remediation: str


class SecurityReviewResult(BaseModel):
    findings: List[SecurityFinding]
    passed: bool
    has_critical_or_high: bool
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class TestResult(BaseModel):
    __test__ = False
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    missing_tests_identified: List[str] = Field(default_factory=list)
    proposed_tests: List[Dict[str, Any]] = Field(default_factory=list)
    passed: bool = False
    stdout: str = ""
    stderr: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)


class RepairResult(BaseModel):
    iteration_number: int
    root_cause: str
    repair_patch: List[FileOperation] = Field(default_factory=list)
    tests_passed: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)


class AgentDecision(BaseModel):
    decision: str  # proceed, repair_required, human_review_required, reject, cancel
    reason: str
    next_agent: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class WorkflowResult(BaseModel):
    run_id: str
    status: str
    overall_progress: int
    final_decision: Optional[AgentDecision] = None
    error_message: Optional[str] = None
