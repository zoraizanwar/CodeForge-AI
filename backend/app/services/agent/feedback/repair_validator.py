"""
Repair validator for CodeForge AI autonomous feedback loop (Step 10).
Enforces security, safety boundaries, and anti-cheating rules on generated repairs.
"""
import re
import logging
from typing import List, Dict, Any
from app.schemas.agent import FileChangeSchema, RootCauseAnalysisSchema
from app.services.agent.validator import validate_proposed_change, ChangeValidationError

logger = logging.getLogger("codeforge.feedback.validator")

MAX_REPAIR_FILES = 10
MAX_REPAIR_FILE_SIZE = 500 * 1024  # 500 KB
MAX_REPAIR_TOTAL_SIZE = 2 * 1024 * 1024  # 2 MB


class RepairValidationError(Exception):
    """Raised when a repair patch fails safety or anti-cheating validation."""
    pass


def validate_repair_patch(
    changes: List[FileChangeSchema],
    analysis: RootCauseAnalysisSchema,
    workspace_path: str
) -> None:
    """
    Enforces strict security checks, file size limits, anti-cheating rules, and path safety on repair patches.
    """
    # 1. Confidence threshold check
    if analysis.confidence < 0.6:
        raise RepairValidationError(f"AI diagnostic confidence ({analysis.confidence:.2f}) is below safe threshold (0.60). Human review required.")

    if not changes:
        raise RepairValidationError("Generated repair patch contains no file changes.")

    if len(changes) > MAX_REPAIR_FILES:
        raise RepairValidationError(f"Repair patch modifies {len(changes)} files, exceeding limit of {MAX_REPAIR_FILES}.")

    total_size = 0

    for change in changes:
        f_path = change.file_path.replace("\\", "/")
        f_lower = f_path.lower()

        # 2. Prevent test file deletion
        if change.operation == "delete":
            if "test" in f_lower or f_lower.endswith("_test.go") or f_lower.endswith(".test.ts"):
                raise RepairValidationError(f"Refusing to delete test file '{change.file_path}' to make test suite pass.")

        content = change.proposed_content or ""
        content_bytes = content.encode("utf-8")

        if len(content_bytes) > MAX_REPAIR_FILE_SIZE:
            raise RepairValidationError(f"File '{change.file_path}' size ({len(content_bytes)} bytes) exceeds single file limit ({MAX_REPAIR_FILE_SIZE} bytes).")

        total_size += len(content_bytes)

        # 3. Anti-cheating: Prevent removing assertions or skipping tests
        if "test" in f_lower:
            # Check for unconditional test skips introduced in repair
            if re.search(r"@pytest\.mark\.skip", content) or re.search(r"\bit\.skip\(", content) or re.search(r"\bdescribe\.skip\(", content):
                raise RepairValidationError(f"Refusing repair that adds test skip directives in '{change.file_path}'.")

        # 4. Anti-weakening of security controls
        diff_lower = (change.diff or "").lower()
        if any(sec_term in diff_lower for sec_term in ["get_safe_workspace_path", "validate_path", "jwt_secret"]):
            if "-" in diff_lower and any(kw in diff_lower for kw in ["raise", "http-exception", "return false"]):
                raise RepairValidationError(f"Refusing repair that attempts to weaken security validation in '{change.file_path}'.")

        # 5. Existing Step 7 multi-layer validation
        try:
            validate_proposed_change(
                repo_local_path=workspace_path,
                file_path=change.file_path,
                operation=change.operation,
                proposed_content=change.proposed_content
            )
        except ChangeValidationError as cve:
            raise RepairValidationError(f"Security validation failed for '{change.file_path}': {cve}")

    if total_size > MAX_REPAIR_TOTAL_SIZE:
        raise RepairValidationError(f"Total repair patch size ({total_size} bytes) exceeds limit ({MAX_REPAIR_TOTAL_SIZE} bytes).")
