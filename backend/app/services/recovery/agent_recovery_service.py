"""
Agent Run & Workflow Checkpoint Recovery Service for Step 20.
Preserves completed steps, plans, and sandbox results, resuming workflows from safe checkpoints.
"""
import uuid
import datetime
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.agent import AgentTask, AgentExecution, AgentIteration, GitOperation
from app.models.multi_agent import AgentRun, AgentRunStep
from app.models.recovery import RecoveryEvent
from app.models.repository import Repository

logger = logging.getLogger("codeforge.recovery.agent_recovery")


class AgentRecoveryService:
    @classmethod
    def recover_interrupted_tasks(cls, db: Session) -> Dict[str, Any]:
        """
        Scans for AgentTasks left in transient execution/repair states after host or worker crash.
        Resumes from safe checkpoints without re-generating plans or bypassing approval gates.
        """
        interrupted_tasks = db.query(AgentTask).filter(
            AgentTask.status.in_(["executing", "generating", "planning", "repairing"])
        ).all()

        recovered_count = 0
        details: List[Dict[str, Any]] = []

        for task in interrupted_tasks:
            repo = db.query(Repository).filter(Repository.id == task.repository_id).first()
            org_id = repo.organization_id if repo else None
            prev_status = task.status

            if task.is_approved and task.plan:
                # Task plan was already approved by user. Reset to 'approved' or 'execution_failed' for safe retry
                task.status = "approved"
                action = "reset_to_approved_checkpoint"
            elif task.files_to_modify or task.changes:
                # Task generated changes but not yet approved. Reset to 'ready_for_review'
                task.status = "ready_for_review"
                action = "reset_to_ready_for_review"
            else:
                task.status = "pending"
                action = "reset_to_pending"

            db.commit()
            recovered_count += 1

            rec_event = RecoveryEvent(
                organization_id=org_id,
                user_id=task.user_id,
                event_type="agent_task_checkpoint_recovery",
                resource_type="agent_task",
                resource_id=str(task.id),
                status="completed",
                details={
                    "previous_status": prev_status,
                    "recovered_status": task.status,
                    "action": action,
                    "is_approved": task.is_approved
                }
            )
            db.add(rec_event)
            db.commit()

            details.append({"task_id": str(task.id), "prev": prev_status, "recovered": task.status})

        logger.info(f"AgentTask recovery scan completed. Recovered {recovered_count} task(s).")
        return {"recovered_count": recovered_count, "details": details}

    @classmethod
    def recover_interrupted_agent_runs(cls, db: Session) -> Dict[str, Any]:
        """
        Scans multi-agent workflows (AgentRun) left in running status. Resumes or marks failed safely.
        """
        interrupted_runs = db.query(AgentRun).filter(AgentRun.status == "running").all()
        recovered_count = 0

        for run in interrupted_runs:
            repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
            org_id = repo.organization_id if repo else None

            # Inspect steps to see if any failed
            steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).all()
            completed_steps = [s for s in steps if s.status == "completed"]
            failed_steps = [s for s in steps if s.status == "failed"]

            if failed_steps:
                run.status = "failed"
                run.error_message = "Multi-agent run failed due to step execution errors after worker restart."
            elif len(completed_steps) == len(steps) and len(steps) > 0:
                run.status = "completed"
            else:
                # Mark as paused/degraded for manual resumption
                run.status = "paused"

            db.commit()
            recovered_count += 1

            rec_event = RecoveryEvent(
                organization_id=org_id,
                user_id=run.user_id,
                event_type="agent_run_checkpoint_recovery",
                resource_type="agent_run",
                resource_id=str(run.id),
                status="completed",
                details={
                    "recovered_status": run.status,
                    "completed_steps": len(completed_steps),
                    "total_steps": len(steps)
                }
            )
            db.add(rec_event)
            db.commit()

        return {"recovered_count": recovered_count}
