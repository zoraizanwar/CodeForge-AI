"""
Execution service package for safe workspace execution and automated testing (Step 8).
"""
from app.services.execution.workspace_manager import create_execution_workspace, cleanup_execution_workspace
from app.services.execution.patch_applier import apply_task_patch
from app.services.execution.command_runner import run_sandboxed_command
from app.services.execution.test_detector import detect_project_and_test_commands
from app.services.execution.result_parser import parse_execution_results
from app.services.execution.manager import execute_agent_task_execution_pipeline

__all__ = [
    "create_execution_workspace",
    "cleanup_execution_workspace",
    "apply_task_patch",
    "run_sandboxed_command",
    "detect_project_and_test_commands",
    "parse_execution_results",
    "execute_agent_task_execution_pipeline"
]
