"""
Repair Orchestrator for CodeForge AI (Step 10).
Coordinates failure analysis, repair planning, patch generation, safety validation,
isolated execution, and iteration limit enforcement.
"""
import os
import uuid
import datetime
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.agent import AgentTask, AgentExecution, AgentIteration
from app.models.repository import Repository
from app.services.repository import get_safe_workspace_path
from app.services.agent.feedback.feedback_analyzer import FeedbackAnalyzer
from app.services.agent.feedback.repair_planner import RepairPlanner
from app.services.agent.feedback.repair_generator import RepairGenerator
from app.services.agent.feedback.repair_validator import validate_repair_patch, RepairValidationError
from app.services.execution.manager import execute_agent_task_execution_pipeline
from app.services.git.patch_fingerprint import compute_patch_hash

logger = logging.getLogger("codeforge.feedback.orchestrator")
MAX_REPAIR_ITERATIONS = 3


def read_task_files(repo_local_path: str, files: List[str]) -> Dict[str, str]:
    """Safely reads file contents for relative file paths within workspace."""
    contents = {}
    for f in files:
        try:
            abs_p = get_safe_workspace_path(repo_local_path, f)
            if os.path.exists(abs_p) and os.path.isfile(abs_p):
                with open(abs_p, "r", encoding="utf-8", errors="replace") as fh:
                    contents[f] = fh.read()
        except Exception:
            pass
    return contents


async def execute_repair_loop(
    task_id: uuid.UUID,
    db: Optional[Session] = None
) -> None:
    """
    Asynchronous background pipeline for autonomous repair iteration.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found for repair loop.")
            return

        repo = db.query(Repository).filter(Repository.id == task.repository_id).first()
        if not repo or not repo.local_path:
            task.status = "failed"
            task.error_message = "Repository workspace not found."
            db.commit()
            return

        # Fetch latest failed execution
        trigger_exec = db.query(AgentExecution).filter(
            AgentExecution.task_id == task.id
        ).order_by(AgentExecution.created_at.desc()).first()

        if not trigger_exec:
            task.status = "failed"
            task.error_message = "No execution record exists to analyze."
            db.commit()
            return

        # Determine iteration number
        existing_count = db.query(AgentIteration).filter(AgentIteration.task_id == task.id).count()
        iteration_number = existing_count + 1

        iteration = AgentIteration(
            task_id=task.id,
            iteration_number=iteration_number,
            trigger_execution_id=trigger_exec.id,
            status="analyzing",
            started_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(iteration)
        task.status = "repairing"
        db.commit()
        db.refresh(iteration)

        # Enforce max repair iterations limit
        if iteration_number > MAX_REPAIR_ITERATIONS:
            iteration.status = "stopped"
            iteration.error_message = f"Maximum repair iteration limit reached ({MAX_REPAIR_ITERATIONS}/{MAX_REPAIR_ITERATIONS}). Human review required."
            iteration.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.status = "human_review_required"
            db.commit()
            return

        # 1. Failure Analysis
        analyzer = FeedbackAnalyzer()
        analysis = await analyzer.analyze_execution_failure(
            task_description=task.task_description,
            stdout=trigger_exec.stdout,
            stderr=trigger_exec.stderr,
            test_summary=trigger_exec.test_summary,
            previous_changes=task.changes or []
        )

        iteration.failure_category = analysis.failure_category
        iteration.failure_summary = f"[{analysis.failure_category}] {analysis.root_cause[:300]}"
        iteration.root_cause = analysis.root_cause

        if analysis.confidence < 0.6:
            iteration.status = "stopped"
            iteration.error_message = f"AI confidence score ({analysis.confidence:.2f}) below threshold (0.60). Stopping for human review."
            iteration.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.status = "human_review_required"
            db.commit()
            return

        # 2. Repair Planning
        iteration.status = "planning"
        db.commit()

        planner = RepairPlanner()
        plan = await planner.create_repair_plan(
            task_description=task.task_description,
            analysis=analysis,
            previous_changes=task.changes or []
        )
        iteration.plan = plan

        # 3. Repair Patch Generation
        iteration.status = "generating"
        db.commit()

        file_contents = read_task_files(repo.local_path, task.files_to_modify or [])
        generator = RepairGenerator()
        repair_changes = await generator.generate_repair_patch(
            task_description=task.task_description,
            repair_plan=plan,
            root_cause_analysis=analysis.model_dump(),
            previous_changes=task.changes or [],
            file_contents=file_contents
        )

        # 4. Repair Validation
        iteration.status = "validating"
        db.commit()

        raw_changes_dict = [c.model_dump() for c in repair_changes]
        validate_repair_patch(repair_changes, analysis, repo.local_path)

        iteration.files_changed = raw_changes_dict
        iteration.patch_hash = compute_patch_hash(raw_changes_dict)

        # Update task changes to the newly validated repair patch
        task.changes = raw_changes_dict
        task.is_approved = False  # Reset approval state for new repair patch
        task.approved_patch_hash = None
        db.commit()

        # 5. Isolated Sandbox Execution
        iteration.status = "executing"
        db.commit()

        exec_record = AgentExecution(
            task_id=task.id,
            status="pending",
            workspace_path="pending_allocation"
        )
        db.add(exec_record)
        db.commit()
        db.refresh(exec_record)

        iteration.execution_id = exec_record.id
        db.commit()

        # Execute repair patch inside fresh sandbox workspace
        await execute_agent_task_execution_pipeline(exec_record.id, db=db)

        db.refresh(exec_record)
        db.refresh(iteration)

        # Evaluate execution outcome
        if exec_record.status == "passed":
            iteration.status = "passed"
            iteration.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.status = "execution_passed"
        else:
            if iteration_number >= MAX_REPAIR_ITERATIONS:
                iteration.status = "stopped"
                iteration.error_message = f"Repair iteration {iteration_number} failed. Reached max limit ({MAX_REPAIR_ITERATIONS}). Human review required."
                task.status = "human_review_required"
            else:
                iteration.status = "failed"
                task.status = "execution_failed"

            iteration.completed_at = datetime.datetime.now(datetime.timezone.utc)

        db.commit()

    except RepairValidationError as rve:
        logger.warning(f"Repair validation stopped iteration: {rve}")
        if 'iteration' in locals() and iteration:
            iteration.status = "stopped"
            iteration.error_message = str(rve)
            iteration.completed_at = datetime.datetime.now(datetime.timezone.utc)
        if 'task' in locals() and task:
            task.status = "human_review_required"
        db.commit()
    except Exception as exc:
        logger.error(f"Repair loop unexpected error for task {task_id}: {exc}", exc_info=True)
        if 'iteration' in locals() and iteration:
            iteration.status = "failed"
            iteration.error_message = str(exc)
            iteration.completed_at = datetime.datetime.now(datetime.timezone.utc)
        if 'task' in locals() and task:
            task.status = "failed"
        db.commit()
    finally:
        if should_close_db:
            db.close()
