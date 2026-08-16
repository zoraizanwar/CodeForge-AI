"""
Commit manager for CodeForge AI Git & PR automation (Step 9).
Formats commit messages and verifies changed files against security rules before committing.
"""
import re
import logging
from typing import List, Dict, Any
from app.services.repository import EXCLUDED_FILES, EXCLUDED_EXTENSIONS

logger = logging.getLogger("codeforge.git.commit")


class CommitValidationError(Exception):
    """Raised when commit verification fails."""
    pass


def format_commit_message(task_description: str) -> str:
    """
    Sanitizes and formats a safe commit message.
    Format: CodeForge: {task_description}
    """
    if not task_description:
        return "CodeForge: Automated patch implementation"

    # Clean multi-line or control characters
    cleaned = re.sub(r"[\r\n\t]+", " ", task_description).strip()
    # Truncate title length to 80 chars
    title = cleaned[:80] if len(cleaned) > 80 else cleaned
    return f"CodeForge: {title}"


def verify_commit_files_safety(changed_files: List[str]) -> None:
    """
    Verifies that no sensitive files (.env, .pem, private keys) are included in the commit list.
    """
    for f in changed_files:
        f_lower = f.lower()
        base_name = f_lower.split("/")[-1].split("\\")[-1]

        if base_name in EXCLUDED_FILES or base_name.startswith(".env"):
            raise CommitValidationError(f"Refusing to commit sensitive file '{f}'.")

        ext = "." + base_name.split(".")[-1] if "." in base_name else ""
        if ext in EXCLUDED_EXTENSIONS:
            raise CommitValidationError(f"Refusing to commit file with forbidden extension '{f}'.")
