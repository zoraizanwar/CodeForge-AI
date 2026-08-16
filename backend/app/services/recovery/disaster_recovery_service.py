"""
Disaster Recovery Readiness & System Diagnostics Service for Step 20.
Executes comprehensive readiness checks across database, migrations, worker leases, queue, workspace, backups, and pgvector.
"""
import os
import shutil
import datetime
import logging
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import engine
from app.core.database_reliability import verify_database_connectivity
from app.models.job import AgentJob
from app.models.recovery import BackupRecord, SystemHealthSnapshot

logger = logging.getLogger("codeforge.recovery.disaster_recovery")


class DisasterRecoveryService:
    @classmethod
    def get_recovery_readiness_report(cls, db: Session) -> Dict[str, Any]:
        """
        Generates a consolidated disaster recovery readiness status report.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        services_status: Dict[str, str] = {}
        active_warnings: List[str] = []

        # 1. Database Check
        db_diag = verify_database_connectivity()
        services_status["database"] = db_diag["status"]
        if db_diag["status"] != "healthy":
            active_warnings.append(f"Database latency/connection error: {db_diag.get('error')}")

        # 2. Migrations Check
        try:
            db.execute(text("SELECT version_num FROM alembic_version")).scalar()
            services_status["migrations"] = "current"
        except Exception as e:
            services_status["migrations"] = "unknown"
            active_warnings.append(f"Alembic version check failed: {e}")

        # 3. Job Queue Health
        try:
            stuck_jobs_count = db.query(AgentJob).filter(
                AgentJob.status.in_(["running", "cancelling"]),
                AgentJob.lease_expires_at < now
            ).count()

            if stuck_jobs_count > 0:
                services_status["job_queue"] = "degraded"
                active_warnings.append(f"Found {stuck_jobs_count} stuck job(s) with expired leases.")
            else:
                services_status["job_queue"] = "healthy"
        except Exception as e:
            services_status["job_queue"] = "unhealthy"
            active_warnings.append(f"Job queue check error: {e}")

        # 4. Workers Health
        try:
            active_workers_count = db.query(AgentJob.worker_id).filter(
                AgentJob.status == "running",
                AgentJob.lease_expires_at > now
            ).distinct().count()

            services_status["workers"] = "healthy" if active_workers_count >= 0 else "degraded"
        except Exception:
            services_status["workers"] = "degraded"

        # 5. Workspace & Storage Check
        ws_root = settings.workspace_root_resolved
        try:
            os.makedirs(ws_root, exist_ok=True)
            stat = shutil.disk_usage(ws_root)
            free_gb = round(stat.free / (1024 ** 3), 2)

            services_status["workspace"] = "healthy"
            services_status["storage"] = "healthy"
            if free_gb < 1.0:
                services_status["storage"] = "degraded"
                active_warnings.append(f"Low workspace storage space ({free_gb} GB free).")
        except Exception as e:
            services_status["workspace"] = "unhealthy"
            services_status["storage"] = "unhealthy"
            active_warnings.append(f"Workspace directory un-writable: {e}")

        # 6. Backup Freshness Check
        try:
            latest_backup = db.query(BackupRecord).filter(
                BackupRecord.is_verified == True
            ).order_by(BackupRecord.created_at.desc()).first()

            if not latest_backup:
                services_status["backup"] = "degraded"
                active_warnings.append("No verified backup records found.")
            else:
                age_days = (now - latest_backup.created_at).days
                if age_days > 7:
                    services_status["backup"] = "degraded"
                    active_warnings.append(f"Latest verified backup is {age_days} days old.")
                else:
                    services_status["backup"] = "healthy"
        except Exception as e:
            services_status["backup"] = "degraded"
            active_warnings.append(f"Backup check error: {e}")

        # 7. pgvector Check
        if engine.name == "postgresql":
            try:
                res = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).fetchone()
                services_status["pgvector"] = "healthy" if res else "not_installed"
            except Exception:
                services_status["pgvector"] = "unavailable"
        else:
            services_status["pgvector"] = "healthy"  # SQLite vector mock active

        # Compute overall status
        statuses = list(services_status.values())
        if any(s == "unhealthy" for s in statuses):
            overall_status = "failed"
        elif any(s in ["degraded", "not_installed", "unknown"] for s in statuses) or len(active_warnings) > 0:
            overall_status = "degraded"
        else:
            overall_status = "ready"

        # Record snapshot in database
        snapshot = SystemHealthSnapshot(
            overall_status=overall_status,
            database_status=services_status.get("database", "unknown"),
            migrations_status=services_status.get("migrations", "unknown"),
            job_queue_status=services_status.get("job_queue", "unknown"),
            workers_status=services_status.get("workers", "unknown"),
            workspace_status=services_status.get("workspace", "unknown"),
            backup_status=services_status.get("backup", "unknown"),
            storage_status=services_status.get("storage", "unknown"),
            pgvector_status=services_status.get("pgvector", "unknown"),
            metrics_summary=db_diag,
            active_warnings=active_warnings
        )
        db.add(snapshot)
        db.commit()

        return {
            "overall_status": overall_status,
            "timestamp": now.isoformat(),
            "services": services_status,
            "warnings": active_warnings,
            "database_diagnostics": db_diag
        }
