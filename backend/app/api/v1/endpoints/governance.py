import uuid
from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.services.authorization.permission_service import PermissionService

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.governance import PolicyDecision, RiskAssessment, WorkflowDecision, ApprovalRecord
from app.services.governance import ReliabilityScoring

router = APIRouter()

@router.get("/decisions")
def list_workflow_decisions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    decisions = db.query(WorkflowDecision).filter(
        WorkflowDecision.user_id == current_user.id
    ).order_by(WorkflowDecision.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": len(decisions),
        "items": [{
            "id": str(d.id),
            "stage": d.stage,
            "decision_type": d.decision_type,
            "confidence_score": d.confidence_score,
            "rationale": d.rationale,
            "escalation_result": d.escalation_result,
            "created_at": d.created_at
        } for d in decisions]
    }

@router.get("/policies")
def list_policy_decisions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    policies = db.query(PolicyDecision).filter(
        PolicyDecision.user_id == current_user.id
    ).order_by(PolicyDecision.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": len(policies),
        "items": [{
            "id": str(p.id),
            "policy_name": p.policy_name,
            "decision": p.decision,
            "reason": p.reason,
            "metadata": p.metadata_,
            "created_at": p.created_at
        } for p in policies]
    }

@router.get("/risk")
def list_risk_assessments(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    risks = db.query(RiskAssessment).filter(
        RiskAssessment.user_id == current_user.id
    ).order_by(RiskAssessment.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": len(risks),
        "items": [{
            "id": str(r.id),
            "risk_level": r.risk_level,
            "factors": r.factors,
            "impact_analysis": r.impact_analysis,
            "created_at": r.created_at
        } for r in risks]
    }

@router.get("/approvals")
def list_approvals(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    approvals = db.query(ApprovalRecord).filter(
        ApprovalRecord.user_id == current_user.id
    ).order_by(ApprovalRecord.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": len(approvals),
        "items": [{
            "id": str(a.id),
            "scope": a.scope,
            "status": a.status,
            "reason": a.reason,
            "created_at": a.created_at,
            "updated_at": a.updated_at
        } for a in approvals]
    }

@router.get("/reliability")
def get_reliability_metrics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    metrics = ReliabilityScoring.get_agent_reliability(db, current_user.id)
    return metrics

@router.post("/approvals/{approval_id}/approve")
def approve_action(
    approval_id: uuid.UUID,
    reason: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    approval = db.query(ApprovalRecord).filter(
        ApprovalRecord.id == approval_id,
        ApprovalRecord.user_id == current_user.id
    ).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval record not found")
        
    approval.status = "approved"
    approval.approver_id = current_user.id
    approval.reason = reason
    db.commit()
    
    return {"status": "success", "message": "Action approved"}

@router.post("/approvals/{approval_id}/reject")
def reject_action(
    approval_id: uuid.UUID,
    reason: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    approval = db.query(ApprovalRecord).filter(
        ApprovalRecord.id == approval_id,
        ApprovalRecord.user_id == current_user.id
    ).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval record not found")
        
    approval.status = "rejected"
    approval.approver_id = current_user.id
    approval.reason = reason
    db.commit()
    
    return {"status": "success", "message": "Action rejected"}
