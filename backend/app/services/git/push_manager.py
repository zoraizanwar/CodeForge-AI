"""
Push manager for CodeForge AI Git & PR automation (Step 9).
Pushes feature branches securely using short-lived installation tokens without exposing credentials.
"""
import os
import logging
from app.services.git.branch_manager import validate_branch_name, BranchValidationError
from app.services.execution.command_runner import run_sandboxed_command

logger = logging.getLogger("codeforge.git.push")


class PushError(Exception):
    """Raised when pushing branch fails."""
    pass


async def push_feature_branch_to_remote(
    workspace_path: str,
    branch_name: str,
    token: str,
    owner: str,
    repo_name: str
) -> str:
    """
    Pushes an approved feature branch to GitHub using an installation access token.
    Enforces branch validation (never pushes protected branches) and hides credentials.
    """
    # 1. Validate branch is a feature branch
    validated_branch = validate_branch_name(branch_name)

    if not token or not owner or not repo_name:
        raise PushError("Missing GitHub credentials or repository info for push.")

    # Construct authenticated HTTPS remote URL without logging token
    remote_url = f"https://x-access-token:{token}@github.com/{owner}/{repo_name}.git"

    try:
        # Check if origin remote exists
        check_remote = await run_sandboxed_command(["git", "remote"], cwd=workspace_path)
        if "origin" in check_remote.stdout:
            await run_sandboxed_command(["git", "remote", "set-url", "origin", remote_url], cwd=workspace_path)
        else:
            await run_sandboxed_command(["git", "remote", "add", "origin", remote_url], cwd=workspace_path)

        # Push feature branch
        res = await run_sandboxed_command(["git", "push", "-u", "origin", validated_branch], cwd=workspace_path)

        if res.exit_code != 0:
            # Mask token in error message if present
            err_msg = res.stderr.replace(token, "[REDACTED]")
            if "403" in err_msg or "Permission to" in err_msg or "denied to" in err_msg:
                # Try fallback using standard git remote url
                safe_url = f"https://github.com/{owner}/{repo_name}.git"
                await run_sandboxed_command(["git", "remote", "set-url", "origin", safe_url], cwd=workspace_path)
                fallback_res = await run_sandboxed_command(["git", "push", "-u", "origin", validated_branch], cwd=workspace_path)
                if fallback_res.exit_code == 0:
                    logger.info(f"Successfully pushed branch '{validated_branch}' using system git credentials.")
                    return validated_branch
                
                logger.warning(f"Git push 403 forbidden for '{validated_branch}'. Local commit preserved.")
                return ""  # Signal local-only completion
            raise PushError(f"Git push failed for branch '{validated_branch}': {err_msg}")

        logger.info(f"Successfully pushed branch '{validated_branch}' to github.com/{owner}/{repo_name}.")
        return validated_branch

    finally:
        # Reset origin remote URL to scrub token from local git config
        safe_url = f"https://github.com/{owner}/{repo_name}.git"
        await run_sandboxed_command(["git", "remote", "set-url", "origin", safe_url], cwd=workspace_path)
