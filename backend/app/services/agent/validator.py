"""
Security and sanity validator for AI Software Engineer Agent proposed code changes (Step 7).
Enforces path boundaries, sensitive file rejections, operation constraints, and volume limits.
"""
import os
import logging
from typing import List, Dict, Any
from app.services.repository import get_safe_workspace_path, EXCLUDED_FOLDERS, EXCLUDED_FILES

logger = logging.getLogger(__name__)

MAX_CHANGED_FILES = 20
MAX_FILE_SIZE_BYTES = 500_000  # 500 KB per file



class ChangeValidationError(Exception):
    """Exception raised when a proposed file change fails validation."""
    pass


def validate_proposed_change(
    repo_local_path: str,
    file_path: str,
    operation: str,
    proposed_content: str
) -> str:
    """
    Validates a single proposed file change.
    Returns the resolved safe absolute path within workspace if valid.
    Raises ChangeValidationError on failure.
    """
    if not file_path or not file_path.strip():
        raise ChangeValidationError("File path cannot be empty.")

    file_path = file_path.strip()

    # 1. Path safety validation (absolute paths, traversals, UNC, boundary escape)
    try:
        safe_abs_path = get_safe_workspace_path(repo_local_path, file_path)
    except PermissionError as pe:
        raise ChangeValidationError(f"Invalid path for '{file_path}': {str(pe)}")
    except Exception as e:
        raise ChangeValidationError(f"Path boundary check failed for '{file_path}': {str(e)}")

    # 2. Excluded directory / filename checks
    norm_path = file_path.replace("\\", "/")
    parts = [p.lower() for p in norm_path.split("/") if p]
    filename = parts[-1] if parts else ""

    for exc_dir in EXCLUDED_FOLDERS:
        if exc_dir.lower() in parts:
            raise ChangeValidationError(f"Target path '{file_path}' touches excluded directory '{exc_dir}'.")

    if filename.lower() in EXCLUDED_FILES or filename.startswith(".env"):
        raise ChangeValidationError(f"Target path '{file_path}' touches protected sensitive file '{filename}'.")

    for ext in [".pem", ".key", ".pfx", ".p12", ".crt"]:
        if filename.lower().endswith(ext):
            raise ChangeValidationError(f"Target path '{file_path}' touches sensitive key/cert file extension '{ext}'.")

    # 3. File size limit check
    if proposed_content and len(proposed_content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        raise ChangeValidationError(
            f"Proposed content for '{file_path}' exceeds maximum size limit of {MAX_FILE_SIZE_BYTES} bytes."
        )

    # 4. Operation-specific checks
    if operation == "modify":
        if not os.path.exists(safe_abs_path) or not os.path.isfile(safe_abs_path):
            logger.info(f"File '{file_path}' does not exist for 'modify' operation; treating as file creation.")
    elif operation == "delete":
        if not os.path.exists(safe_abs_path):
            logger.info(f"File '{file_path}' does not exist for 'delete' operation; treating as already deleted.")
    elif operation == "create":
        pass
    else:
        raise ChangeValidationError(f"Invalid operation '{operation}'. Must be 'create', 'modify', or 'delete'.")


    return safe_abs_path


def validate_proposed_changes(
    repo_local_path: str,
    changes: List[Dict[str, Any]]
) -> None:
    """
    Validates the complete set of proposed file changes.
    Raises ChangeValidationError if any change is invalid or if total volume exceeds limits.
    """
    if not isinstance(changes, list):
        raise ChangeValidationError("Malformed changes output: expected a list of file changes.")

    if len(changes) > MAX_CHANGED_FILES:
        raise ChangeValidationError(
            f"Proposed changes count ({len(changes)}) exceeds maximum allowed ({MAX_CHANGED_FILES})."
        )

    seen_paths = set()
    for item in changes:
        if not isinstance(item, dict):
            raise ChangeValidationError("Malformed file change item: expected a dictionary.")

        file_path = item.get("file_path")
        operation = item.get("operation")
        proposed_content = item.get("proposed_content", "")

        if not file_path or not operation:
            raise ChangeValidationError("File change item must specify 'file_path' and 'operation'.")

        if file_path in seen_paths:
            raise ChangeValidationError(f"Duplicate file change proposed for path '{file_path}'.")
        seen_paths.add(file_path)

        validate_proposed_change(repo_local_path, file_path, operation, proposed_content)
