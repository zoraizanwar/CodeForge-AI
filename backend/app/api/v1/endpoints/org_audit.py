import uuid
from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.audit import AuditEvent
from app.services.authorization.permission_service import PermissionService

router = APIRouter()

@router.get("/{org_id}/audit")
def list_organization_audit(
    org_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    event_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    # Only owner/admin can access organization-wide audit logs
    PermissionService.require_organization_role(db, current_user.id, org_id, "admin")
    
    query = db.query(AuditEvent).filter(AuditEvent.organization_id == org_id)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
        
    total = query.count()
    events = query.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "event_type": e.event_type,
                
                
                
                "success": e.success,
                "created_at": e.created_at,
                "user_id": e.user_id,
                "repository_id": e.repository_id
            } for e in events
        ]
    }
