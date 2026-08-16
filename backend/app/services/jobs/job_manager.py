"""
Job Manager service for CodeForge AI (Step 11).
Handles job creation, duplicate operation prevention, tenant isolation, cancellation, and retries.
"""
import uuid
import datetime
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.job import AgentJob
from app.models.agent import AgentTask
from app.models.repository import Repository
from app.core.config import settings
from app.services.jobs.progress import update_job_progress
from app.services.jobs.cancellation import cancel_job_execution, is_job_cancelled_in_memory, clear_cancelled_job_flag

logger = logging.getLogger("codeforge.jobs.manager")


class JobManager:
    @staticmethod
    def enqueue_job(
        db: Session,
        user_id: uuid.UUID,
        repository_id: uuid.UUID,
        job_type: str,
        task_id: Optional[uuid.UUID] = None,
        priority: int = 0,
        payload: Optional[Dict[str, Any]] = None,
        max_attempts: Optional[int] = None
    ) -> AgentJob:
        """
        Creates and enqueues a persistent job in PostgreSQL with duplicate operation protection.
        """
        # Validate repository ownership
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.user_id == user_id
        ).first()
        if not repo:
            raise PermissionError("Repository not found or access denied.")

        # Duplicate job protection
        if job_type in ["pull_request", "repair", "agent_task", "execution"]:
            existing_active = db.query(AgentJob).filter(
                AgentJob.repository_id == repository_id,
                AgentJob.job_type == job_type,
                AgentJob.status.in_(["queued", "running", "retrying"])
            )
            if task_id:
                existing_active = existing_active.filter(AgentJob.task_id == task_id)

            if existing_active.first():
                raise ValueError(f"An active '{job_type}' job is already running for this task/repository.")

        job = AgentJob(
            id=uuid.uuid4(),
            user_id=user_id,
            repository_id=repository_id,
            task_id=task_id,
            job_type=job_type,
            status="queued",
            progress=0,
            current_stage="queued",
            attempt_count=0,
            max_attempts=max_attempts or settings.JOB_MAX_ATTEMPTS,
            priority=priority,
            payload=payload or {}
        )
        db.add(job)

        # Synchronize task status if applicable
        if task_id:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                if job_type == "agent_task":
                    task.status = "analyzing"
                elif job_type == "execution":
                    task.status = "executing"
                elif job_type == "repair":
                    task.status = "repairing"

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_job(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AgentJob]:
        """Retrieves a job by ID enforcing tenant isolation."""
        return db.query(AgentJob).filter(
            AgentJob.id == job_id,
            AgentJob.user_id == user_id
        ).first()

    @staticmethod
    def list_jobs(
        db: Session,
        user_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AgentJob]:
        """Lists jobs for an authenticated user with filtering."""
        query = db.query(AgentJob).filter(AgentJob.user_id == user_id)
        if repository_id:
            query = query.filter(AgentJob.repository_id == repository_id)
        if job_type:
            query = query.filter(AgentJob.job_type == job_type)
        if status:
            query = query.filter(AgentJob.status == status)

        return query.order_by(AgentJob.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    async def cancel_job(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> AgentJob:
        """
        Cooperatively cancels a queued or running job.
        """
        job = JobManager.get_job(db, job_id, user_id)
        if not job:
            raise PermissionError("Job not found or access denied.")

        if job.status in ["completed", "failed", "cancelled"]:
            raise ValueError(f"Cannot cancel job in state '{job.status}'.")

        job.status = "cancelling"
        job.current_stage = "cancelling"
        db.commit()

        # Perform subprocess & workspace cleanup
        workspace_path = (job.payload or {}).get("workspace_path")
        await cancel_job_execution(job.id, workspace_path=workspace_path)

        job.status = "cancelled"
        job.current_stage = "cancelled"
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.error_message = "Job cancelled by user request."
        db.commit()
        db.refresh(job)

        # Update task status if associated
        if job.task_id:
            task = db.query(AgentTask).filter(AgentTask.id == job.task_id).first()
            if task and task.status not in ["pr_created", "approved"]:
                task.status = "failed"
                task.error_message = "Task operation cancelled."
                db.commit()

        await update_job_progress(db, job.id, job.progress, "cancelled", message="Job cancelled by user.", status="cancelled")

        return job

    @staticmethod
    async def retry_job(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> AgentJob:
        """
        Manually retries a failed or cancelled job.
        """
        job = JobManager.get_job(db, job_id, user_id)
        if not job:
            raise PermissionError("Job not found or access denied.")

        if job.status not in ["failed", "cancelled"]:
            raise ValueError(f"Only failed or cancelled jobs can be retried. Current state: '{job.status}'.")

        clear_cancelled_job_flag(job.id)

        job.status = "queued"
        job.progress = 0
        job.current_stage = "queued"
        job.error_message = None
        job.result = None
        job.started_at = None
        job.completed_at = None
        job.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        db.refresh(job)

        await update_job_progress(db, job.id, 0, "queued", message="Job re-queued for execution.", status="queued")

        return job
