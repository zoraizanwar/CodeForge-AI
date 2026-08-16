"""
Branch manager for CodeForge AI Git & PR automation (Step 9).
Validates branch names and enforces feature branch creation rules.
"""
import re
import uuid
from typing import Optional

FORBIDDEN_BRANCH_NAMES = {
    "main",
    "master",
    "develop",
    "production",
    "release",
    "staging"
}

FORBIDDEN_BRANCH_PREFIXES = (
    "main/",
    "master/",
    "develop/",
    "production/",
    "release/",
    "staging/"
)


class BranchValidationError(Exception):
    """Raised when a branch name fails security or syntax checks."""
    pass


def validate_branch_name(branch_name: str) -> str:
    """
    Validates that a branch name is a safe, non-protected feature branch ref.
    """
    if not branch_name or not isinstance(branch_name, str):
        raise BranchValidationError("Branch name must be a non-empty string.")

    b = branch_name.strip()

    # Reject leading hyphens
    if b.startswith("-"):
        raise BranchValidationError("Branch name cannot start with a hyphen.")

    # Reject protected branches
    b_lower = b.lower()
    if b_lower in FORBIDDEN_BRANCH_NAMES or b_lower.startswith(FORBIDDEN_BRANCH_PREFIXES):
        raise BranchValidationError(f"Modification or push to protected branch '{b}' is strictly forbidden.")

    # Reject traversals and invalid ref patterns
    if ".." in b or "@{" in b or "~" in b or "^" in b or ":" in b or "?" in b or "*" in b or "[" in b or "\\" in b:
        raise BranchValidationError(f"Branch name '{b}' contains forbidden Git ref characters.")

    # Allow alphanumeric, slashes, hyphens, underscores
    if not re.match(r"^[a-zA-Z0-9_\-/]+$", b):
        raise BranchValidationError(f"Branch name '{b}' contains invalid characters.")

    return b


def generate_feature_branch_name(task_id: uuid.UUID, suffix: Optional[str] = None) -> str:
    """
    Generates a standardized feature branch name for an agent task.
    Format: codeforge/task-{short_id}
    """
    short_id = str(task_id).split("-")[0]
    base = f"codeforge/task-{short_id}"
    if suffix:
        clean_suffix = re.sub(r"[^a-zA-Z0-9_-]", "", suffix)
        base = f"{base}-{clean_suffix}"
    return validate_branch_name(base)
