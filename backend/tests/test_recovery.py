import os
import uuid
import pytest
import datetime
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.job import AgentJob
from app.models.agent import AgentTask
from app.models.multi_agent import AgentRun
from app.models.recovery import RecoveryEvent, BackupRecord
from app.core.database_reliability import verify_database_connectivity, with_db_retry
from app.services.recovery.job_recovery_service import JobRecoveryService
from app.services.recovery.agent_recovery_service import AgentRecoveryService
from app.services.recovery.workspace_cleanup_service import WorkspaceCleanupService
from app.services.recovery.backup_service import BackupService
from app.services.recovery.disaster_recovery_service import DisasterRecoveryService


def test_database_connectivity_and_reliability():
    diag = verify_database_connectivity()
    assert diag["status"] == "healthy"
    assert diag["latency_ms"] >= 0.0

    count = 0
    @with_db_retry(max_retries=2, initial_backoff=0.01)
    def dummy_func():
        nonlocal count
        count += 1
        return "success"

    res = dummy_func()
    assert res == "success"
    assert count == 1


def test_job_lease_and_stale_job_recovery(db_session, test_user):
    repo = Repository(name="Job Recovery Repo", full_name="test/job-recovery", github_repo_id=10001, owner="test", default_branch="main", local_path="/tmp/repo1", user_id=test_user.id)
    db_session.add(repo)
    db_session.commit()

    job = AgentJob(
        user_id=test_user.id,
        repository_id=repo.id,
        job_type="analysis",
        status="running",
        worker_id="worker_alpha",
        last_heartbeat=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=300),
        lease_expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=240),
        attempt_count=1,
        max_attempts=3
    )
    db_session.add(job)
    db_session.commit()

    # Recover stale jobs
    res = JobRecoveryService.recover_stale_jobs(db_session)
    assert res["recovered_count"] >= 1

    db_session.refresh(job)
    assert job.status == "retrying"
    assert job.worker_id is None
    assert job.lease_expires_at is None


def test_git_pr_job_non_retryable_recovery(db_session, test_user):
    repo = Repository(name="PR Recovery Repo", full_name="test/pr-recovery", github_repo_id=10002, owner="test", default_branch="main", local_path="/tmp/repo2", user_id=test_user.id)
    db_session.add(repo)
    db_session.commit()

    job = AgentJob(
        user_id=test_user.id,
        repository_id=repo.id,
        job_type="pull_request",
        status="running",
        worker_id="worker_beta",
        lease_expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=100),
        attempt_count=1,
        max_attempts=3
    )
    db_session.add(job)
    db_session.commit()

    res = JobRecoveryService.recover_stale_jobs(db_session)
    db_session.refresh(job)
    # Pull Request jobs must NEVER be blindly retried
    assert job.status == "failed"
    assert "Manual review required" in job.error_message


def test_agent_checkpoint_recovery(db_session, test_user):
    repo = Repository(name="Agent Recovery Repo", full_name="test/agent-recovery", github_repo_id=10003, owner="test", default_branch="main", local_path="/tmp/repo3", user_id=test_user.id)
    db_session.add(repo)
    db_session.commit()

    task = AgentTask(
        user_id=test_user.id,
        repository_id=repo.id,
        task_description="Interrupted task test",
        status="executing",
        is_approved=True,
        plan={"steps": ["plan_step_1"]}
    )
    db_session.add(task)
    db_session.commit()

    res = AgentRecoveryService.recover_interrupted_tasks(db_session)
    assert res["recovered_count"] >= 1

    db_session.refresh(task)
    # Approved plan tasks reset to approved checkpoint for safe retry
    assert task.status == "approved"


def test_workspace_cleanup_and_path_safety():
    from app.core.config import settings
    root = settings.workspace_root_resolved

    # Path safety test
    safe_subpath = os.path.join(root, "sandbox_123")
    unsafe_traversal = os.path.join(root, "../../../etc/passwd")

    assert WorkspaceCleanupService.is_path_safe_for_cleanup(safe_subpath) is True
    assert WorkspaceCleanupService.is_path_safe_for_cleanup(unsafe_traversal) is False
    assert WorkspaceCleanupService.is_path_safe_for_cleanup(root) is False


def test_backup_creation_and_verification(db_session, test_user):
    org = Organization(name="Backup Org")
    db_session.add(org)
    db_session.commit()

    backup = BackupService.create_backup(db_session, organization_id=org.id, user_id=test_user.id, backup_type="database")
    assert backup is not None
    assert backup.is_verified is True
    assert len(backup.checksum_sha256) == 64
    assert os.path.exists(backup.file_path)

    # Re-verify
    verified = BackupService.verify_backup(db_session, backup.id)
    assert verified.is_verified is True

    # Preflight plan
    plan = BackupService.generate_restore_preflight_plan(db_session, backup.id)
    assert plan["requires_explicit_admin_confirmation"] is True
    assert plan["is_verified"] is True


def test_disaster_recovery_readiness(db_session):
    report = DisasterRecoveryService.get_recovery_readiness_report(db_session)
    assert "overall_status" in report
    assert "services" in report
    assert report["services"]["database"] == "healthy"
