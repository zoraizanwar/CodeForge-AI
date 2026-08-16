"""
Job queue worker claim & concurrency manager for CodeForge AI (Step 11).
Uses SELECT ... FOR UPDATE SKIP LOCKED in PostgreSQL to safely claim jobs without contention.
Enforces per-user and per-repository concurrency limits.
"""
import uuid
import datetime
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.job import AgentJob
from app.core.config import settings

logger = logging.getLogger("codeforge.jobs.queue")


def count_running_jobs_for_user(db: Session, user_id: uuid.UUID) -> int:
    """Counts active running or retrying jobs for a specific user."""
    return db.query(AgentJob).filter(
        AgentJob.user_id == user_id,
        AgentJob.status.in_(["running", "retrying"])
    ).count()


def count_running_jobs_for_repository(db: Session, repo_id: uuid.UUID) -> int:
    """Counts active running or retrying jobs for a specific repository."""
    return db.query(AgentJob).filter(
        AgentJob.repository_id == repo_id,
        AgentJob.status.in_(["running", "retrying"])
    ).count()


def claim_next_job(db: Session) -> Optional[AgentJob]:
    """
    Safely claims the highest-priority, oldest queued job.
    Uses PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED to prevent two workers from claiming the same job.
    Enforces user and repository concurrency limits.
    """
    try:
        bind = db.get_bind()
        is_postgres = bind.dialect.name == "postgresql"

        if is_postgres:
            # PostgreSQL FOR UPDATE SKIP LOCKED row locking
            stmt = text("""
                SELECT id FROM agent_jobs
                WHERE status IN ('queued', 'retrying')
                ORDER BY priority DESC, created_at ASC
                FOR UPDATE SKIP LOCKED
            """)
            result = db.execute(stmt)
            job_ids = [row[0] for row in result.fetchall()]
        else:
            # Fallback for SQLite / unit testing
            candidates = db.query(AgentJob.id).filter(
                AgentJob.status.in_(["queued", "retrying"])
            ).order_by(AgentJob.priority.desc(), AgentJob.created_at.asc()).all()
            job_ids = [c[0] for c in candidates]

        for j_id in job_ids:
            job = db.query(AgentJob).filter(AgentJob.id == j_id).first()
            if not job or job.status not in ["queued", "retrying"]:
                continue

            # Check per-user concurrency limit
            if count_running_jobs_for_user(db, job.user_id) >= settings.JOB_MAX_CONCURRENT_PER_USER:
                logger.debug(f"Skipping job {job.id}: user {job.user_id} reached concurrency limit.")
                continue

            # Check per-repository concurrency limit
            if count_running_jobs_for_repository(db, job.repository_id) >= settings.JOB_MAX_CONCURRENT_PER_REPOSITORY:
                logger.debug(f"Skipping job {job.id}: repo {job.repository_id} reached concurrency limit.")
                continue

            # Claim job
            job.status = "running"
            job.started_at = datetime.datetime.now(datetime.timezone.utc)
            job.attempt_count += 1
            job.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            db.refresh(job)
            return job

    except Exception as e:
        db.rollback()
        logger.error(f"Error claiming next job from queue: {e}", exc_info=True)

    return None
