"""
Audit Event Retention & Cleanup Service for CodeForge AI Step 14 Observability.
Safely purges expired audit event records older than configured retention period (AUDIT_RETENTION_DAYS).
Supports dry-run verification mode and never touches operational entities or repository source code.
"""
import logging
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent
from app.core.config import settings

logger = logging.getLogger("codeforge.audit.cleanup")


def cleanup_expired_audit_events(
    db: Session,
    retention_days: Optional[int] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Purges audit_events records older than retention_days (default settings.AUDIT_RETENTION_DAYS).
    """
    days = retention_days if retention_days is not None else settings.AUDIT_RETENTION_DAYS
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    try:
        query = db.query(AuditEvent).filter(AuditEvent.created_at < cutoff_date)
        expired_count = query.count()

        if dry_run:
            logger.info(f"Audit Cleanup DRY RUN: Found {expired_count} expired audit events older than {days} days (cutoff: {cutoff_date}).")
            return {
                "deleted_count": expired_count,
                "retention_days": days,
                "cutoff_date": cutoff_date.isoformat(),
                "dry_run": True
            }

        if expired_count > 0:
            query.delete(synchronize_session=False)
            db.commit()
            logger.info(f"Audit Cleanup: Successfully purged {expired_count} expired audit event records older than {days} days.")

        return {
            "deleted_count": expired_count,
            "retention_days": days,
            "cutoff_date": cutoff_date.isoformat(),
            "dry_run": False
        }
    except Exception as exc:
        logger.error(f"Failed to execute audit event cleanup: {exc}", exc_info=True)
        db.rollback()
        raise
