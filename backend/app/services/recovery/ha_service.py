"""
High Availability & Distributed Leader Lease Service for Step 20.
Coordinates periodic tasks and worker scheduling across multi-instance API deployments.
"""
import uuid
import datetime
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.recovery import RecoveryEvent

logger = logging.getLogger("codeforge.recovery.ha")

LEADER_LEASE_KEY = "global_system_leader"
LEADER_LEASE_DURATION_SECONDS = 30


class HAService:
    @staticmethod
    def acquire_leader_lease(db: Session, instance_id: str, lease_seconds: int = LEADER_LEASE_DURATION_SECONDS) -> bool:
        """
        Attempts to acquire or extend global system leader lease for background scheduling tasks.
        Returns True if instance is leader, False otherwise.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Check existing leader lease event
        leader_event = db.query(RecoveryEvent).filter(
            RecoveryEvent.event_type == "leader_lease",
            RecoveryEvent.resource_type == "ha_leader"
        ).order_by(RecoveryEvent.created_at.desc()).first()

        if leader_event and leader_event.details:
            expires_str = leader_event.details.get("expires_at")
            owner_id = leader_event.details.get("instance_id")
            
            if expires_str and owner_id and owner_id != instance_id:
                try:
                    exp_dt = datetime.datetime.fromisoformat(expires_str)
                    if exp_dt > now:
                        return False
                except Exception:
                    pass

        # Lease is free or expired or owned by instance -> acquire
        exp_dt = now + datetime.timedelta(seconds=lease_seconds)
        new_event = RecoveryEvent(
            event_type="leader_lease",
            resource_type="ha_leader",
            resource_id=instance_id,
            status="completed",
            details={
                "instance_id": instance_id,
                "acquired_at": now.isoformat(),
                "expires_at": exp_dt.isoformat()
            }
        )
        db.add(new_event)
        db.commit()
        return True
