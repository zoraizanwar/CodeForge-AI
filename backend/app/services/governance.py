import uuid
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.governance import (
    PolicyDecision, RiskAssessment, WorkflowDecision, ApprovalRecord
)
from app.models.multi_agent import AgentRun, AgentRunStep
from app.services.audit import record_event

class PolicyEngine:
    DEFAULT_BLOCKED_PATTERNS = [
        ".env", "secrets/", "*.pem", "*.key", "*.crt", "credentials", "aws_access"
    ]
    
    @classmethod
    def evaluate_patch(cls, db: Session, user_id: uuid.UUID, repository_id: uuid.UUID, agent_run_id: uuid.UUID, file_paths: List[str], patch_content: str) -> PolicyDecision:
        """Evaluates basic repository protection policies."""
        decision = "allow"
        reasons = []
        
        # Check blocked files
        for path in file_paths:
            path_lower = path.lower()
            if any(pattern.replace("*", "") in path_lower for pattern in cls.DEFAULT_BLOCKED_PATTERNS):
                decision = "deny"
                reasons.append(f"Blocked file pattern detected: {path}")
                
        # Check size limits
        if len(file_paths) > 10:
            decision = "deny"
            reasons.append(f"Exceeded max files modified (limit: 10, actual: {len(file_paths)})")
            
        if len(patch_content.splitlines()) > 1000:
            if decision != "deny":
                decision = "require_review"
            reasons.append("Patch size exceeds 1000 lines")
            
        reason_str = " | ".join(reasons) if reasons else "Policy checks passed"
        
        policy_decision = PolicyDecision(
            user_id=user_id,
            repository_id=repository_id,
            agent_run_id=agent_run_id,
            policy_name="repository_protection",
            decision=decision,
            reason=reason_str,
            metadata_={"files_checked": len(file_paths), "patch_size": len(patch_content)}
        )
        db.add(policy_decision)
        
        record_event(
            db=db,
            event_type="governance.policy_evaluation",
            severity="warning" if decision != "allow" else "info",
            user_id=user_id,
            repository_id=repository_id,
            request_id=None,
            success=True,
            metadata={"decision": decision, "reason": reason_str}
        )
        
        return policy_decision

class RiskClassificationEngine:
    AUTH_KEYWORDS = ["auth", "login", "jwt", "token", "password", "session"]
    INFRA_KEYWORDS = ["docker", "kubernetes", "terraform", "nginx", "k8s"]
    DB_KEYWORDS = ["migration", "alembic", "schema", "table"]
    
    @classmethod
    def classify(cls, db: Session, user_id: uuid.UUID, repository_id: uuid.UUID, agent_run_id: uuid.UUID, file_paths: List[str], patch_content: str) -> RiskAssessment:
        factors = []
        risk_score = 0
        
        content_lower = patch_content.lower()
        paths_lower = [p.lower() for p in file_paths]
        
        # Check auth
        if any(kw in content_lower for kw in cls.AUTH_KEYWORDS) or any(kw in p for p in paths_lower for kw in cls.AUTH_KEYWORDS):
            factors.append("Authentication/Authorization code modified")
            risk_score += 2
            
        # Check Infra
        if any(kw in content_lower for kw in cls.INFRA_KEYWORDS) or any(kw in p for p in paths_lower for kw in cls.INFRA_KEYWORDS):
            factors.append("Infrastructure code modified")
            risk_score += 2
            
        # Check DB
        if any(kw in content_lower for kw in cls.DB_KEYWORDS) or any(kw in p for p in paths_lower for kw in cls.DB_KEYWORDS):
            factors.append("Database schema/migration modified")
            risk_score += 2
            
        # Volume
        if len(file_paths) >= 5:
            factors.append("High volume of files changed")
            risk_score += 1
            
        if risk_score == 0:
            risk_level = "low"
        elif risk_score <= 2:
            risk_level = "medium"
        elif risk_score <= 4:
            risk_level = "high"
        else:
            risk_level = "critical"
            
        assessment = RiskAssessment(
            user_id=user_id,
            repository_id=repository_id,
            agent_run_id=agent_run_id,
            risk_level=risk_level,
            factors=factors,
            impact_analysis={"affected_files": len(file_paths)}
        )
        db.add(assessment)
        
        record_event(
            db=db,
            event_type="governance.risk_assessment",
            severity="info",
            user_id=user_id,
            repository_id=repository_id,
            request_id=None,
            success=True,
            metadata={"risk_level": risk_level, "factors": factors}
        )
        return assessment

class ChangeImpactAnalysis:
    @staticmethod
    def analyze(file_paths: List[str]) -> Dict[str, Any]:
        """Simple static analysis to estimate impact."""
        modules = list(set([p.split("/")[0] for p in file_paths if "/" in p]))
        return {
            "affected_modules": modules,
            "affected_files_count": len(file_paths),
            "estimated_impact": "high" if len(modules) > 3 else "medium" if len(modules) > 1 else "low"
        }

class ReliabilityScoring:
    @staticmethod
    def get_agent_reliability(db: Session, user_id: uuid.UUID) -> Dict[str, Any]:
        runs = db.query(AgentRun).filter(AgentRun.user_id == user_id).all()
        total_runs = len(runs)
        if total_runs == 0:
            return {"success_rate": 100.0, "total": 0}
            
        success_count = sum(1 for r in runs if r.status == "completed")
        failure_count = sum(1 for r in runs if r.status == "failed")
        
        success_rate = (success_count / total_runs) * 100.0
        return {
            "success_rate": round(success_rate, 2),
            "total_runs": total_runs,
            "success_count": success_count,
            "failure_count": failure_count
        }

class WorkflowEscalator:
    @staticmethod
    def evaluate(db: Session, user_id: uuid.UUID, repository_id: uuid.UUID, agent_run_id: uuid.UUID, stage: str, policy: PolicyDecision, risk: RiskAssessment, confidence: float) -> WorkflowDecision:
        escalation = "continue"
        rationale = "Normal execution."
        
        if policy.decision == "deny":
            escalation = "blocked"
            rationale = f"Policy violation: {policy.reason}"
        elif policy.decision == "require_review" or risk.risk_level in ["high", "critical"]:
            escalation = "human_review_required"
            rationale = f"High risk ({risk.risk_level}) or policy requirement."
        elif confidence < 0.6:
            escalation = "require_review"
            rationale = "Low agent confidence."
            
        decision = WorkflowDecision(
            user_id=user_id,
            repository_id=repository_id,
            agent_run_id=agent_run_id,
            stage=stage,
            decision_type="escalation",
            confidence_score=confidence,
            rationale=rationale,
            escalation_result=escalation
        )
        db.add(decision)
        
        record_event(
            db=db,
            event_type="governance.workflow_escalation",
            severity="warning" if escalation != "continue" else "info",
            user_id=user_id,
            repository_id=repository_id,
            request_id=None,
            success=True,
            metadata={"escalation": escalation, "rationale": rationale}
        )
        return decision

class SecurityReviewHardening:
    @staticmethod
    def analyze_patch(patch_content: str) -> List[str]:
        findings = []
        content_lower = patch_content.lower()
        
        # SSRF checks
        if "requests.get" in content_lower and "url" in content_lower:
            findings.append("Potential SSRF vector: Ensure URL is validated before requests.get")
            
        # SQLi
        if "execute(" in content_lower and "%s" not in content_lower and "?" not in content_lower:
            if "select " in content_lower or "insert " in content_lower or "update " in content_lower:
                findings.append("Potential SQL Injection: Ensure parameterized queries are used")
                
        # Command execution
        if "subprocess.run" in content_lower or "os.system" in content_lower:
            findings.append("Command execution detected: Ensure strict input sanitization")
            
        return findings

class PullRequestGovernance:
    @staticmethod
    def verify_pr_readiness(db: Session, agent_run_id: uuid.UUID) -> Tuple[bool, str]:
        """Verifies if a PR is allowed to be created."""
        run = db.query(AgentRun).filter(AgentRun.id == agent_run_id).first()
        if not run:
            return False, "Agent run not found."
            
        # Check approval
        approval = db.query(ApprovalRecord).filter(
            ApprovalRecord.agent_run_id == agent_run_id,
            ApprovalRecord.scope == "pull_request",
            ApprovalRecord.status == "approved"
        ).first()
        
        if not approval:
            return False, "Human approval is required for PR creation."
            
        # Check policies
        policies = db.query(PolicyDecision).filter(PolicyDecision.agent_run_id == agent_run_id).all()
        for p in policies:
            if p.decision == "deny":
                return False, f"Policy violation blocks PR: {p.reason}"
                
        # Check workflow escalations
        escalations = db.query(WorkflowDecision).filter(WorkflowDecision.agent_run_id == agent_run_id).all()
        for e in escalations:
            if e.escalation_result == "blocked":
                return False, f"Workflow was blocked: {e.rationale}"
                
        return True, "PR checks passed."
