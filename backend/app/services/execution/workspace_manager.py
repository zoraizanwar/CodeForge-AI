"""
Workspace manager for CodeForge AI Agent safe execution environment (Step 8).
Manages creation, safe copying, and cleanup of isolated execution workspaces.
"""
import os
import shutil
import uuid
import logging
from app.services.repository import (
    get_safe_workspace_path,
    EXCLUDED_FOLDERS,
    EXCLUDED_EXTENSIONS,
    EXCLUDED_FILES
)

logger = logging.getLogger("codeforge.execution.workspace")


def get_executions_base_dir() -> str:
    """Returns the base directory for execution workspaces."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    executions_dir = os.path.join(project_root, "workspaces", "executions")
    os.makedirs(executions_dir, exist_ok=True)
    return executions_dir


def create_execution_workspace(repo_local_path: str, execution_id: uuid.UUID) -> str:
    """
    Creates an isolated execution workspace folder and copies non-excluded files from original repo.
    Never modifies the original repository workspace.
    """
    if not repo_local_path or not os.path.exists(repo_local_path):
        raise ValueError("Original repository workspace does not exist.")

    base_dir = get_executions_base_dir()
    exec_folder_name = f"exec_{execution_id}"
    target_workspace = os.path.join(base_dir, exec_folder_name)

    if os.path.exists(target_workspace):
        shutil.rmtree(target_workspace, ignore_errors=True)

    os.makedirs(target_workspace, exist_ok=True)

    # Safely copy repository files excluding heavy/sensitive folders & binary artifacts
    base_src = os.path.realpath(repo_local_path)
    for root, dirs, files in os.walk(base_src):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS and not d.startswith(".")]

        rel_dir = os.path.relpath(root, base_src)
        target_dir = os.path.join(target_workspace, rel_dir) if rel_dir != "." else target_workspace
        os.makedirs(target_dir, exist_ok=True)

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in EXCLUDED_EXTENSIONS or f in EXCLUDED_FILES or f.startswith(".env"):
                continue

            src_file = os.path.join(root, f)
            dest_file = os.path.join(target_dir, f)

            # Skip symlinks to prevent symlink escape vulnerabilities
            if os.path.islink(src_file):
                continue

            try:
                shutil.copy2(src_file, dest_file)
            except Exception as exc:
                logger.warning(f"Could not copy file '{f}' to execution workspace: {str(exc)}")

    logger.info(f"Created isolated execution workspace at '{target_workspace}' for execution {execution_id}.")
    return target_workspace


def cleanup_execution_workspace(workspace_path: str) -> None:
    """
    Safely deletes temporary execution workspace directory.
    Validates boundary to prevent accidental deletion outside the executions folder.
    """
    if not workspace_path or not os.path.exists(workspace_path):
        return

    base_dir = os.path.realpath(get_executions_base_dir())
    target_dir = os.path.realpath(workspace_path)

    try:
        common = os.path.commonpath([base_dir, target_dir])
        if os.path.realpath(common) != base_dir or target_dir == base_dir:
            logger.error(f"Refusing to delete path outside execution boundary: '{target_dir}'")
            return
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.info(f"Cleaned up execution workspace at '{target_dir}'.")
    except Exception as e:
        logger.error(f"Failed to cleanup execution workspace '{workspace_path}': {str(e)}")
