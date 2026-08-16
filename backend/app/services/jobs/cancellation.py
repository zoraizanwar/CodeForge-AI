"""
Cooperative cancellation manager for CodeForge AI jobs (Step 11).
Tracks active running processes/subprocesses and handles safe process termination and cleanup.
"""
import os
import shutil
import logging
import asyncio
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger("codeforge.jobs.cancellation")

# Registry tracking active asyncio Subprocesses or Task handles per job_id
_ACTIVE_SUBPROCESSES: Dict[str, Any] = {}
_CANCELLED_JOB_IDS: set = set()


def register_job_process(job_id: uuid.UUID, proc: Any) -> None:
    """Registers an active process handle associated with a running job."""
    _ACTIVE_SUBPROCESSES[str(job_id)] = proc


def unregister_job_process(job_id: uuid.UUID) -> None:
    """Unregisters a process handle when a job completes or terminates."""
    _ACTIVE_SUBPROCESSES.pop(str(job_id), None)


def mark_job_cancelled(job_id: uuid.UUID) -> None:
    """Flag job_id as cancelled in memory for immediate cooperative cancellation checks."""
    _CANCELLED_JOB_IDS.add(str(job_id))


def is_job_cancelled_in_memory(job_id: uuid.UUID) -> bool:
    """Checks if job_id was flagged for cancellation."""
    return str(job_id) in _CANCELLED_JOB_IDS


def clear_cancelled_job_flag(job_id: uuid.UUID) -> None:
    """Clears the in-memory cancellation flag when job status is resolved."""
    _CANCELLED_JOB_IDS.discard(str(job_id))


async def cancel_job_execution(job_id: uuid.UUID, workspace_path: Optional[str] = None) -> bool:
    """
    Terminates running subprocesses associated with job_id and cleans up temporary workspaces.
    """
    str_id = str(job_id)
    mark_job_cancelled(job_id)

    proc = _ACTIVE_SUBPROCESSES.get(str_id)
    if proc:
        try:
            logger.info(f"Terminating running subprocess for job {job_id}...")
            if hasattr(proc, "terminate"):
                proc.terminate()
            elif hasattr(proc, "kill"):
                proc.kill()
        except Exception as e:
            logger.warning(f"Error terminating subprocess for job {job_id}: {e}")
        finally:
            unregister_job_process(job_id)

    # Clean up temporary execution workspace if provided
    if workspace_path and os.path.exists(workspace_path):
        try:
            logger.info(f"Cleaning up workspace '{workspace_path}' for cancelled job {job_id}...")
            if os.path.isdir(workspace_path):
                shutil.rmtree(workspace_path, ignore_errors=True)
            elif os.path.isfile(workspace_path):
                os.remove(workspace_path)
        except Exception as e:
            logger.error(f"Error cleaning workspace for job {job_id}: {e}")

    return True
