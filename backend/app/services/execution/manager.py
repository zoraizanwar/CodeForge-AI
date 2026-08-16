"""
Orchestration manager for CodeForge AI safe execution pipeline (Step 8).
Manages execution lifecycle: pending -> preparing -> applying -> testing -> passed/failed.
"""
import uuid
import datetime
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.agent import AgentTask, AgentExecution
from app.models.repository import Repository
from app.services.execution.workspace_manager import create_execution_workspace, cleanup_execution_workspace
from app.services.execution.patch_applier import apply_task_patch
from app.services.execution.test_detector import detect_project_and_test_commands
from app.services.execution.command_runner import run_sandboxed_command, CommandResult
from app.services.execution.result_parser import parse_execution_results

logger = logging.getLogger("codeforge.execution.manager")


async def execute_agent_task_execution_pipeline(
    execution_id: uuid.UUID,
    db: Optional[Session] = None
) -> None:
    """
    Executes an approved AgentTask patch inside an isolated temporary workspace.
    Captures command outputs, test summary, and updates task and execution status.
    Cleans up the temporary workspace automatically.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
        if not execution:
            logger.error(f"Execution record {execution_id} not found.")
            return

        task = db.query(AgentTask).filter(AgentTask.id == execution.task_id).first()
        if not task:
            execution.status = "failed"
            execution.error_message = "Associated agent task not found."
            db.commit()
            return

        repo = db.query(Repository).filter(Repository.id == task.repository_id).first()
        if not repo or not repo.local_path:
            execution.status = "failed"
            execution.error_message = "Repository workspace not found on server."
            task.status = "failed"
            db.commit()
            return

        # Phase 1: Preparing
        execution.status = "preparing"
        execution.started_at = datetime.datetime.now(datetime.timezone.utc)
        task.status = "executing"
        db.commit()

        # Create isolated workspace
        workspace_path = create_execution_workspace(repo.local_path, execution.id)
        execution.workspace_path = workspace_path
        db.commit()

        # Phase 2: Applying Patch
        execution.status = "applying"
        db.commit()

        if not task.changes:
            execution.status = "failed"
            execution.error_message = "No code changes available in task to execute."
            task.status = "ready_for_review"
            cleanup_execution_workspace(workspace_path)
            db.commit()
            return

        apply_task_patch(workspace_path, task.changes)

        # Phase 3: Testing & Command Execution
        execution.status = "testing"
        db.commit()

        config = detect_project_and_test_commands(workspace_path)

        command_results: List[CommandResult] = []

        # Run discovered prep commands (if any)
        for cmd in config.prep_commands:
            res = await run_sandboxed_command(cmd, cwd=workspace_path)
            command_results.append(res)
            if res.exit_code != 0:
                logger.warning(f"Prep command '{res.command}' failed.")

        # Run discovered test commands
        for cmd in config.test_commands:
            res = await run_sandboxed_command(cmd, cwd=workspace_path)
            command_results.append(res)

        # Run discovered lint commands (if available)
        for cmd in config.lint_commands:
            res = await run_sandboxed_command(cmd, cwd=workspace_path)
            command_results.append(res)

        # Phase 4: Parsing Results & Summary
        test_summary = parse_execution_results(command_results)

        # Convert CommandResult objects to dict list for JSON column storage
        cmd_results_dict = [
            {
                "command": r.command,
                "exit_code": r.exit_code,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "duration_seconds": r.duration_seconds
            }
            for r in command_results
        ]

        stdout_aggregate = "\n---\n".join(r.stdout for r in command_results if r.stdout)
        stderr_aggregate = "\n---\n".join(r.stderr for r in command_results if r.stderr)

        execution.command_results = cmd_results_dict
        execution.test_summary = test_summary
        execution.stdout = stdout_aggregate
        execution.stderr = stderr_aggregate
        execution.exit_code = 0 if test_summary["passed"] else 1
        execution.completed_at = datetime.datetime.now(datetime.timezone.utc)

        if test_summary["passed"]:
            execution.status = "passed"
            task.status = "tests_passed"
        else:
            execution.status = "failed"
            task.status = "tests_failed"
            execution.error_message = f"Tests or commands failed. {test_summary['tests_failed']} test(s) failed."

        db.commit()

        # Clean up temporary execution workspace
        cleanup_execution_workspace(workspace_path)

    except Exception as exc:
        logger.error(f"Execution pipeline error for execution {execution_id}: {str(exc)}", exc_info=True)
        if 'execution' in locals() and execution:
            execution.status = "failed"
            execution.error_message = str(exc)
            execution.completed_at = datetime.datetime.now(datetime.timezone.utc)
        if 'task' in locals() and task:
            task.status = "tests_failed"
        if 'workspace_path' in locals() and workspace_path:
            cleanup_execution_workspace(workspace_path)
        db.commit()
    finally:
        if should_close_db:
            db.close()
