"""
Workspace Cleanup & Recovery Service for Step 20.
Identifies abandoned sandboxes and temporary execution directories, enforcing strict root containment.
"""
import os
import shutil
import time
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.agent import AgentExecution
from app.models.job import AgentJob
from app.models.recovery import RecoveryEvent

logger = logging.getLogger("codeforge.recovery.workspace_cleanup")

DEFAULT_RETENTION_HOURS = 24


class WorkspaceCleanupService:
    @staticmethod
    def is_path_safe_for_cleanup(target_path: str) -> bool:
        """
        Verifies that target_path is strictly within CodeForge's resolved workspace root.
        Prevents path traversal attacks and accidental system directory deletions.
        """
        if not target_path:
            return False
        
        try:
            root_real = os.path.realpath(settings.workspace_root_resolved)
            target_real = os.path.realpath(target_path)
            
            # Target must be a subpath of root_real, and must NOT be equal to root_real itself
            if target_real == root_real:
                return False
                
            common = os.path.commonpath([root_real, target_real])
            return common == root_real
        except Exception as e:
            logger.error(f"Path safety check failed for '{target_path}': {e}")
            return False

    @classmethod
    def clean_abandoned_workspaces(cls, db: Session, retention_hours: int = DEFAULT_RETENTION_HOURS, dry_run: bool = False) -> Dict[str, Any]:
        """
        Scans workspace directory for abandoned, stale, or crashed sandboxes.
        Safely deletes expired directories after confirming path safety and non-active status.
        """
        root_dir = settings.workspace_root_resolved
        if not os.path.exists(root_dir):
            return {"scanned": 0, "cleaned": 0, "freed_bytes": 0, "dry_run": dry_run}

        # 1. Query active execution workspace paths
        active_execs = db.query(AgentExecution.workspace_path).filter(
            AgentExecution.status.in_(["pending", "preparing", "applying", "testing"])
        ).all()
        active_paths = {os.path.realpath(e[0]) for e in active_execs if e[0]}

        cutoff_time = time.time() - (retention_hours * 3600)
        scanned_count = 0
        cleaned_count = 0
        freed_bytes = 0
        cleaned_dirs: List[str] = []

        try:
            for entry in os.scandir(root_dir):
                if entry.is_dir():
                    scanned_count += 1
                    dir_path = entry.path
                    real_path = os.path.realpath(dir_path)

                    # Safety Check 1: Must be inside workspace root
                    if not cls.is_path_safe_for_cleanup(real_path):
                        logger.warning(f"Cleanup skipped unsafe path: {dir_path}")
                        continue

                    # Safety Check 2: Must not be in active execution set
                    if real_path in active_paths:
                        continue

                    # Safety Check 3: Modified time must be older than cutoff
                    mtime = entry.stat().st_mtime
                    if mtime > cutoff_time:
                        continue

                    # Calculate size before deletion
                    dir_size = 0
                    for root, dirs, files in os.walk(real_path):
                        for f in files:
                            try:
                                dir_size += os.path.getsize(os.path.join(root, f))
                            except Exception:
                                pass

                    if not dry_run:
                        shutil.rmtree(real_path, ignore_errors=True)

                    cleaned_count += 1
                    freed_bytes += dir_size
                    cleaned_dirs.append(dir_path)

        except Exception as e:
            logger.error(f"Error during workspace cleanup: {e}", exc_info=True)

        if cleaned_count > 0 and not dry_run:
            rec_event = RecoveryEvent(
                event_type="workspace_cleanup",
                resource_type="workspace",
                resource_id=root_dir,
                status="completed",
                details={
                    "cleaned_directories_count": cleaned_count,
                    "freed_bytes": freed_bytes,
                    "retention_hours": retention_hours
                }
            )
            db.add(rec_event)
            db.commit()

        return {
            "scanned": scanned_count,
            "cleaned": cleaned_count,
            "freed_bytes": freed_bytes,
            "cleaned_dirs": cleaned_dirs,
            "dry_run": dry_run
        }
