"""
Job Recovery Service for Step 20.
Provides worker lease acquisition, heartbeat renewal, and automatic stale job recovery.
"""
import uuid
import datetime
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.job import AgentJob
from app.models.recovery import RecoveryEvent
from app.models.repository import Repository

logger = logging.getLogger("codeforge.recovery.job_recovery")

DEFAULT_LEASE_SECONDS = 60
STALE_HEARTBEAT_THRESHOLD_SECONDS = 120


class JobRecoveryService:
    @staticmethod
    def acquire_lease(db: Session, job_id: uuid.UUID, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
        """
        Attempts to acquire or extend an exclusive worker lease on a job.
        Returns True if lease acquired, False if claimed by another active worker.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if not job:
            return False

        # If owned by another worker whose lease hasn't expired, cannot acquire
        if job.worker_id and job.worker_id != worker_id:
            if job.lease_expires_at and job.lease_expires_at > now:
                return False

        job.worker_id = worker_id
        job.last_heartbeat = now
        job.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
        db.commit()
        return True

    @staticmethod
    def heartbeat(db: Session, job_id: uuid.UUID, worker_id: str, extend_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
        """
        Renews a worker's active lease heartbeat.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        job = db.query(AgentJob).filter(
            AgentJob.id == job_id,
            AgentJob.worker_id == worker_id
        ).first()

        if not job:
            return False

        job.last_heartbeat = now
        job.lease_expires_at = now + datetime.timedelta(seconds=extend_seconds)
        db.commit()
        return True

    @staticmethod
    def release_lease(db: Session, job_id: uuid.UUID, worker_id: str) -> None:
        """
        Releases a worker's lease upon job completion or cancellation.
        """
        job = db.query(AgentJob).filter(
            AgentJob.id == job_id,
            AgentJob.worker_id == worker_id
        ).first()

        if job:
            job.worker_id = None
            job.lease_expires_at = None
            db.commit()

    @classmethod
    def recover_stale_jobs(cls, db: Session) -> Dict[str, Any]:
        """
        Scans database for stale, interrupted, or lease-expired jobs and safely recovers them.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_cutoff = now - datetime.timedelta(seconds=STALE_HEARTBEAT_THRESHOLD_SECONDS)

        # 1. Query jobs in running or cancelling state with expired leases or stale heartbeats
        stale_jobs = db.query(AgentJob).filter(
            AgentJob.status.in_(["running", "cancelling"]),
            ((AgentJob.lease_expires_at < now) | (AgentJob.last_heartbeat < stale_cutoff) | (AgentJob.lease_expires_at.is_(None)))
        ).all()

        recovered_count = 0
        failed_count = 0
        details_log: List[Dict[str, Any]] = []

        for job in stale_jobs:
            repo = db.query(Repository).filter(Repository.id == job.repository_id).first()
            org_id = repo.organization_id if repo else None

            old_worker = job.worker_id
            job.worker_id = None
            job.lease_expires_at = None

            if job.status == "cancelling":
                job.status = "cancelled"
                job.completed_at = now
                job.error_message = f"Cancelled after worker lease expired (Worker: {old_worker})."
                recovered_count += 1
                action = "cancelled"

            elif job.job_type == "pull_request":
                # Git PR operations must never be blindly retried without manual verification
                job.status = "failed"
                job.completed_at = now
                job.error_message = f"Failed during Git PR operation due to worker disconnect (Worker: {old_worker}). Manual review required."
                failed_count += 1
                action = "failed_git_pr"

            elif job.attempt_count < job.max_attempts:
                job.status = "retrying"
                job.current_stage = "queued"
                job.error_message = f"Recovered after worker heartbeat failure (Worker: {old_worker})."
                recovered_count += 1
                action = "requeued_retry"

            else:
                job.status = "failed"
                job.completed_at = now
                job.error_message = f"Exceeded maximum retries ({job.max_attempts}) after worker disconnect."
                failed_count += 1
                action = "max_retries_exceeded"

            db.commit()

            # Record Recovery Event
            rec_event = RecoveryEvent(
                organization_id=org_id,
                event_type="stale_job_recovery",
                resource_type="agent_job",
                resource_id=str(job.id),
                status="completed",
                details={
                    "job_type": job.job_type,
                    "action_taken": action,
                    "previous_worker": old_worker,
                    "attempt_count": job.attempt_count
                }
            )
            db.add(rec_event)
            db.commit()

            details_log.append({"job_id": str(job.id), "action": action, "old_worker": old_worker})

        logger.info(f"Stale job recovery scan complete. Recovered: {recovered_count}, Failed: {failed_count}.")
        return {
            "recovered_count": recovered_count,
            "failed_count": failed_count,
            "details": details_log
        }
