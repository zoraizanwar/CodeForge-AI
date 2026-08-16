"""
Durable Worker loop for CodeForge AI job orchestration system (Step 11).
Executes persistent background jobs, handles startup recovery for stale/crashed jobs,
enforces retry policies, and monitors cancellation flags.
"""
import os
import sys
import uuid
import asyncio
import datetime
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.job import AgentJob
from app.models.repository import Repository
from app.models.agent import AgentTask
from app.services.jobs.queue import claim_next_job
from app.services.jobs.progress import update_job_progress
from app.services.jobs.cancellation import is_job_cancelled_in_memory, clear_cancelled_job_flag
from app.services.jobs.retry_policy import is_transient_failure, calculate_exponential_backoff
from app.services.analysis import run_analysis_pipeline
from app.services.agent.orchestrator import run_agent_task_pipeline
from app.services.execution.manager import execute_agent_task_execution_pipeline
from app.services.agent.feedback.repair_orchestrator import execute_repair_loop
from app.services.git.manager import execute_git_pr_pipeline

logger = logging.getLogger("codeforge.jobs.worker")

_WORKER_SHUTDOWN_EVENT = asyncio.Event()


def recover_stale_running_jobs(db: Session) -> None:
    """
    On worker startup, finds jobs left in 'running' or 'cancelling' state from a previous crashed worker.
    Delegates to JobRecoveryService to audit and recover stale jobs.
    """
    try:
        from app.services.recovery.job_recovery_service import JobRecoveryService
        JobRecoveryService.recover_stale_jobs(db)
    except Exception as e:
        logger.error(f"Error during stale job recovery: {e}", exc_info=True)



async def _execute_job_handler(db: Session, job: AgentJob) -> Dict[str, Any]:
    """
    Dispatches a job to its corresponding implementation handler.
    Checks cancellation flags between stages.
    """
    j_type = job.job_type
    payload = job.payload or {}

    if is_job_cancelled_in_memory(job.id):
        raise asyncio.CancelledError("Job cancelled before execution.")

    if j_type == "analysis":
        await update_job_progress(db, job.id, 10, "preparing", message="Starting repository analysis...")
        repo = db.query(Repository).filter(Repository.id == job.repository_id).first()
        if not repo:
            raise ValueError(f"Repository {job.repository_id} not found.")

        await update_job_progress(db, job.id, 40, "retrieving_context", message="Parsing AST & symbols...")
        res = await run_analysis_pipeline(repository_id=job.repository_id, user_id=job.user_id, db=db)
        await update_job_progress(db, job.id, 100, "completed", message="Repository analysis completed successfully.")
        return {"status": "success", "analysis": res}

    elif j_type == "agent_task":
        if not job.task_id:
            raise ValueError("agent_task job requires a valid task_id.")
        await update_job_progress(db, job.id, 10, "planning", message="Retrieving context & building plan...")
        await run_agent_task_pipeline(job.task_id, db=db)
        await update_job_progress(db, job.id, 100, "completed", message="Agent planning & code generation complete.")
        return {"status": "success", "task_id": str(job.task_id)}

    elif j_type == "execution":
        if not job.task_id:
            raise ValueError("execution job requires a valid task_id.")
        exec_id = payload.get("execution_id")
        if not exec_id:
            raise ValueError("execution job payload requires execution_id.")
        await update_job_progress(db, job.id, 20, "testing", message="Executing sandboxed tests...")
        await execute_agent_task_execution_pipeline(uuid.UUID(str(exec_id)), db=db)
        await update_job_progress(db, job.id, 100, "completed", message="Sandbox test execution finished.")
        return {"status": "success", "execution_id": str(exec_id)}

    elif j_type == "repair":
        if not job.task_id:
            raise ValueError("repair job requires a valid task_id.")
        await update_job_progress(db, job.id, 20, "analyzing_failure", message="Analyzing failure & planning repair...")
        await execute_repair_loop(job.task_id, db=db)
        await update_job_progress(db, job.id, 100, "completed", message="Autonomous repair iteration finished.")
        return {"status": "success", "task_id": str(job.task_id)}

    elif j_type == "pull_request":
        git_op_id = payload.get("git_operation_id")
        if not git_op_id:
            raise ValueError("pull_request job payload requires git_operation_id.")
        await update_job_progress(db, job.id, 30, "pushing", message="Auditing changes, committing, & creating PR...")
        await execute_git_pr_pipeline(uuid.UUID(str(git_op_id)), db=db)
        await update_job_progress(db, job.id, 100, "completed", message="GitHub Pull Request created successfully.")
        return {"status": "success", "git_operation_id": str(git_op_id)}

    elif j_type == "multi_agent_run":
        run_id = payload.get("run_id")
        if not run_id:
            raise ValueError("multi_agent_run job payload requires run_id.")
        from app.services.agents.orchestrator import run_multi_agent_workflow
        await update_job_progress(db, job.id, 10, "orchestrating", message="Starting multi-agent workflow...")
        wf_res = await run_multi_agent_workflow(uuid.UUID(str(run_id)), db=db)
        await update_job_progress(db, job.id, wf_res.overall_progress, wf_res.status, message=f"Multi-agent workflow status: {wf_res.status}")
        return {"status": "success", "run_id": str(run_id), "workflow_status": wf_res.status}

    else:
        raise ValueError(f"Unknown job type '{j_type}'.")


async def process_single_job(job_id: uuid.UUID, db: Optional[Session] = None) -> None:
    """
    Executes a claimed job in an isolated database session with error handling and retry policies.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if not job:
            return

        logger.info(f"Worker processing job {job.id} (type: {job.job_type}, attempt: {job.attempt_count}/{job.max_attempts})...")

        result = await _execute_job_handler(db, job)

        db.refresh(job)
        job.status = "completed"
        job.progress = 100
        job.current_stage = "completed"
        job.result = result
        job.error_message = None
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        await update_job_progress(db, job.id, 100, "completed", message="Job completed successfully.", status="completed")
        clear_cancelled_job_flag(job.id)

    except asyncio.CancelledError:
        logger.warning(f"Job {job_id} cancelled during execution.")
        db.refresh(job)
        job.status = "cancelled"
        job.current_stage = "cancelled"
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.error_message = "Execution cancelled."
        db.commit()
        await update_job_progress(db, job.id, job.progress, "cancelled", message="Job execution cancelled.", status="cancelled")

    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
        db.refresh(job)

        is_transient = is_transient_failure(exc)
        if is_transient and job.attempt_count < job.max_attempts:
            job.status = "retrying"
            job.current_stage = "queued"
            job.error_message = f"Attempt {job.attempt_count} failed ({str(exc)}). Retrying..."
            db.commit()

            backoff = calculate_exponential_backoff(job.attempt_count)
            logger.info(f"Job {job.id} set to retrying after {backoff:.1f}s backoff.")
            await update_job_progress(db, job.id, job.progress, "retrying", message=f"Transient failure. Retrying in {backoff:.1f}s...", status="retrying")
        else:
            job.status = "failed"
            job.current_stage = "failed"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            job.error_message = str(exc)
            db.commit()

            await update_job_progress(db, job.id, job.progress, "failed", error_message=str(exc), status="failed")

            # Update task status if associated
            if job.task_id:
                task = db.query(AgentTask).filter(AgentTask.id == job.task_id).first()
                if task and task.status not in ["pr_created", "approved"]:
                    task.status = "failed"
                    task.error_message = str(exc)
                    db.commit()
    finally:
        if should_close_db:
            db.close()


async def run_worker_loop(concurrency: int = None) -> None:
    """
    Main background worker loop. Continuously claims queued jobs and executes them up to concurrency limit.
    """
    concurrency_limit = concurrency or settings.JOB_WORKER_CONCURRENCY
    logger.info(f"Starting CodeForge AI Durable Worker Loop (concurrency limit: {concurrency_limit})...")

    db = SessionLocal()
    try:
        recover_stale_running_jobs(db)
    finally:
        db.close()

    active_tasks: set = set()

    while not _WORKER_SHUTDOWN_EVENT.is_set():
        # Remove finished tasks
        active_tasks = {t for t in active_tasks if not t.done()}

        if len(active_tasks) < concurrency_limit:
            db_session = SessionLocal()
            try:
                claimed_job = claim_next_job(db_session)
                if claimed_job:
                    task = asyncio.create_task(process_single_job(claimed_job.id))
                    active_tasks.add(task)
            finally:
                db_session.close()

        await asyncio.sleep(settings.JOB_POLL_INTERVAL)

    # Graceful shutdown: wait for active tasks
    if active_tasks:
        logger.info(f"Worker shutting down... Waiting for {len(active_tasks)} active task(s) to finish...")
        await asyncio.gather(*active_tasks, return_exceptions=True)
    logger.info("Worker loop shut down cleanly.")


def stop_worker_loop() -> None:
    """Signals the worker loop to shut down cleanly."""
    _WORKER_SHUTDOWN_EVENT.set()
