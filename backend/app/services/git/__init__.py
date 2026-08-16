"""
Git service package for branch management, commit verification, push, and GitHub PR creation (Step 9).
"""
from app.services.git.patch_fingerprint import compute_patch_hash
from app.services.git.branch_manager import validate_branch_name, generate_feature_branch_name
from app.services.git.commit_manager import format_commit_message, verify_commit_files_safety
from app.services.git.push_manager import push_feature_branch_to_remote
from app.services.git.manager import execute_git_pr_pipeline

__all__ = [
    "compute_patch_hash",
    "validate_branch_name",
    "generate_feature_branch_name",
    "format_commit_message",
    "verify_commit_files_safety",
    "push_feature_branch_to_remote",
    "execute_git_pr_pipeline"
]
