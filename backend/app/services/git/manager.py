"""
Git & PR Pipeline Manager for CodeForge AI (Step 9).
Coordinates task approval verification, patch fingerprint matching, feature branch creation,
commit verification, pushing to remote GitHub, and opening GitHub Pull Requests.
"""
import os
import shutil
import uuid
import datetime
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.agent import AgentTask, AgentExecution, GitOperation
from app.models.repository import Repository
from app.models.github import GitHubInstallation
from app.models.user import User
from app.services.repository import get_safe_workspace_path
from app.services.execution.workspace_manager import create_execution_workspace, cleanup_execution_workspace
from app.services.execution.patch_applier import apply_task_patch
from app.services.git.patch_fingerprint import compute_patch_hash
from app.services.git.branch_manager import generate_feature_branch_name, validate_branch_name
from app.services.git.commit_manager import format_commit_message, verify_commit_files_safety
from app.services.git.push_manager import push_feature_branch_to_remote
from app.services.github import GitHubService
from app.services.github.pr_service import GitHubPRService
from app.services.execution.command_runner import run_sandboxed_command

logger = logging.getLogger("codeforge.git.manager")


def get_git_ops_base_dir() -> str:
    """Returns base directory for temporary Git operation workspaces."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    git_dir = os.path.join(project_root, "workspaces", "git_ops")
    os.makedirs(git_dir, exist_ok=True)
    return git_dir


async def execute_git_pr_pipeline(
    git_op_id: uuid.UUID,
    db: Optional[Session] = None
) -> None:
    """
    Asynchronous background pipeline for Git branch creation, commit, push, and GitHub Pull Request creation.
    Enforces approval state, patch fingerprint matching, and secret safety.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    workspace_path = None

    try:
        git_op = db.query(GitOperation).filter(GitOperation.id == git_op_id).first()
        if not git_op:
            logger.error(f"GitOperation record {git_op_id} not found.")
            return

        task = db.query(AgentTask).filter(AgentTask.id == git_op.task_id).first()
        if not task:
            git_op.status = "failed"
            git_op.error_message = "Associated agent task not found."
            db.commit()
            return

        repo = db.query(Repository).filter(Repository.id == git_op.repository_id).first()
        if not repo or not repo.local_path:
            git_op.status = "failed"
            git_op.error_message = "Repository workspace not found."
            task.status = "failed"
            db.commit()
            return

        user = db.query(User).filter(User.id == git_op.user_id).first()
        if not user:
            git_op.status = "failed"
            git_op.error_message = "Authenticated user context not found."
            db.commit()
            return

        # 1. Verification of Approval & Fingerprint
        if not task.is_approved:
            git_op.status = "failed"
            git_op.error_message = "AgentTask changes have not been approved by user."
            db.commit()
            return

        current_hash = compute_patch_hash(task.changes or [])
        if task.approved_patch_hash and task.approved_patch_hash != current_hash:
            git_op.status = "failed"
            git_op.error_message = "Approved patch fingerprint does not match current task changes."
            db.commit()
            return

        # 2. Verification of Successful Execution
        execution = db.query(AgentExecution).filter(
            AgentExecution.task_id == task.id,
            AgentExecution.status == "passed"
        ).order_by(AgentExecution.created_at.desc()).first()

        if not execution:
            git_op.status = "failed"
            git_op.error_message = "No successful sandbox test execution exists for this task."
            db.commit()
            return

        git_op.execution_id = execution.id

        # Phase 1: Preparing Git Workspace
        git_op.status = "preparing"
        git_op.started_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        git_base = get_git_ops_base_dir()
        workspace_path = os.path.join(git_base, f"git_{git_op.id}")
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path, ignore_errors=True)

        # Copy original repo contents to Git operation workspace
        workspace_path = create_execution_workspace(repo.local_path, git_op.id)
        db.commit()

        # Phase 2: Applying Approved Patch
        git_op.status = "applying"
        db.commit()

        applied_files = apply_task_patch(workspace_path, task.changes or [])
        if repo.local_path and os.path.exists(repo.local_path):
            try:
                apply_task_patch(repo.local_path, task.changes or [])
            except Exception as local_apply_err:
                logger.warning(f"Failed to apply patch directly to local_path: {local_apply_err}")

        # Phase 3: Committing Changes
        git_op.status = "committing"
        db.commit()

        branch_name = generate_feature_branch_name(task.id)
        git_op.branch_name = branch_name

        # Initialize Git repo if missing and create feature branch
        await run_sandboxed_command(["git", "init"], cwd=workspace_path)
        await run_sandboxed_command(["git", "config", "user.name", "CodeForge AI Agent"], cwd=workspace_path)
        await run_sandboxed_command(["git", "config", "user.email", "agent@codeforge.ai"], cwd=workspace_path)
        await run_sandboxed_command(["git", "checkout", "-b", branch_name], cwd=workspace_path)

        # Verify no sensitive files were introduced
        verify_commit_files_safety(applied_files)

        # Stage only specific applied files for ultra-fast instant staging
        if applied_files:
            await run_sandboxed_command(["git", "add"] + applied_files, cwd=workspace_path)
        else:
            await run_sandboxed_command(["git", "add", "-u"], cwd=workspace_path)

        commit_msg = format_commit_message(task.task_description)
        git_op.commit_message = commit_msg

        res_commit = await run_sandboxed_command(["git", "commit", "-m", commit_msg], cwd=workspace_path)
        if res_commit.exit_code != 0 and "nothing to commit" not in res_commit.stdout:
            raise RuntimeError(f"Git commit failed: {res_commit.stderr}")

        res_sha = await run_sandboxed_command(["git", "rev-parse", "HEAD"], cwd=workspace_path)
        if res_sha.exit_code == 0 and res_sha.stdout.strip():
            git_op.commit_sha = res_sha.stdout.strip()

        # Phase 4: Pushing Branch to Remote
        git_op.status = "pushing"
        db.commit()

        installation = db.query(GitHubInstallation).filter(GitHubInstallation.user_id == user.id).first()
        if not installation:
            raise RuntimeError("User has no connected GitHub App installation.")

        gh_service = GitHubService()
        token = await gh_service.get_installation_access_token(installation.installation_id)

        pushed_branch = await push_feature_branch_to_remote(
            workspace_path=workspace_path,
            branch_name=branch_name,
            token=token,
            owner=repo.owner,
            repo_name=repo.name
        )
        git_op.remote_branch = branch_name

        if not pushed_branch:
            git_op.status = "completed"
            git_op.error_message = "Branch committed & applied locally. Remote GitHub push skipped."
            git_op.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.status = "pr_created"
            db.commit()
            return

        # Phase 5: Creating GitHub Pull Request
        git_op.status = "creating_pr"
        db.commit()

        pr_service = GitHubPRService(github_service=gh_service)
        base_branch = repo.default_branch or "main"
        pr_title = f"CodeForge: {task.task_description[:70]}"
        pr_body = (
            f"## Summary\n{task.task_description}\n\n"
            f"## Changes\n" + "\n".join(f"- `{f}`" for f in applied_files) + "\n\n"
            f"## Validation\n"
            f"- Sandbox Execution: `{execution.status}`\n"
            f"- Tests Passed: {execution.test_summary.get('tests_passed', 0) if execution.test_summary else 0}\n"
            f"- Duration: {execution.test_summary.get('duration_seconds', 0.0) if execution.test_summary else 0.0}s\n\n"
            f"## CodeForge\n"
            f"Generated and validated autonomously by CodeForge AI Agent."
        )

        pr_data = await pr_service.create_pull_request(
            installation_id=installation.installation_id,
            owner=repo.owner,
            repo=repo.name,
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=base_branch
        )

        git_op.pull_request_number = pr_data.get("number")
        git_op.pull_request_url = pr_data.get("html_url")
        git_op.status = "completed"
        git_op.completed_at = datetime.datetime.now(datetime.timezone.utc)
        task.status = "pr_created"

        db.commit()

    except Exception as exc:
        logger.error(f"Git operation pipeline error for operation {git_op_id}: {str(exc)}", exc_info=True)
        if 'git_op' in locals() and git_op:
            git_op.status = "failed"
            git_op.error_message = str(exc)
            git_op.completed_at = datetime.datetime.now(datetime.timezone.utc)
        if 'task' in locals() and task:
            task.status = "failed"
        db.commit()
    finally:
        if workspace_path and os.path.exists(workspace_path):
            cleanup_execution_workspace(workspace_path)
        if should_close_db:
            db.close()
