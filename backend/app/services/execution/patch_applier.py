"""
Patch applier for CodeForge AI safe execution environment (Step 8).
Applies approved AgentTask code changes ONLY inside temporary execution workspaces.
"""
import os
import logging
from typing import List, Dict, Any
from app.services.agent.validator import validate_proposed_changes, validate_proposed_change, ChangeValidationError
from app.services.repository import get_safe_workspace_path

logger = logging.getLogger("codeforge.execution.patch")


def apply_task_patch(
    execution_workspace_path: str,
    changes: List[Dict[str, Any]]
) -> List[str]:
    """
    Applies approved changes inside the isolated temporary execution workspace.
    Validates path security boundaries and returns list of touched relative file paths.
    Raises ChangeValidationError if any change violates security rules or path boundaries.
    """
    if not os.path.exists(execution_workspace_path):
        raise ChangeValidationError("Execution workspace path does not exist.")

    # 1. Validate complete set of changes against volume/size/security rules
    validate_proposed_changes(execution_workspace_path, changes)

    modified_files: List[str] = []

    for item in changes:
        file_path = item["file_path"].strip()
        operation = item["operation"].lower()
        proposed_content = item.get("proposed_content", "")

        # 2. Get safe absolute path strictly inside execution workspace
        safe_abs_path = validate_proposed_change(
            repo_local_path=execution_workspace_path,
            file_path=file_path,
            operation=operation,
            proposed_content=proposed_content
        )

        # Double check boundary
        safe_abs_path = get_safe_workspace_path(execution_workspace_path, file_path)

        if operation in ("create", "modify"):
            # Ensure parent directories exist
            os.makedirs(os.path.dirname(safe_abs_path), exist_ok=True)
            with open(safe_abs_path, "w", encoding="utf-8") as f:
                f.write(proposed_content)
            modified_files.append(file_path)
            logger.info(f"Applied '{operation}' for '{file_path}' in execution workspace.")
        elif operation == "delete":
            if os.path.exists(safe_abs_path):
                if os.path.isfile(safe_abs_path) or os.path.islink(safe_abs_path):
                    os.remove(safe_abs_path)
                elif os.path.isdir(safe_abs_path):
                    import shutil
                    shutil.rmtree(safe_abs_path, ignore_errors=True)
                modified_files.append(file_path)
                logger.info(f"Applied 'delete' for '{file_path}' in execution workspace.")

    return modified_files
