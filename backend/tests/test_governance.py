import pytest
import uuid
from sqlalchemy.orm import Session
from app.services.governance import PolicyEngine, RiskClassificationEngine, WorkflowEscalator, ChangeImpactAnalysis, ReliabilityScoring, SecurityReviewHardening

def test_policy_engine(db_session: Session):
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()
    
    # Test safe patch
    decision = PolicyEngine.evaluate_patch(
        db_session, user_id, repo_id, agent_run_id, 
        ["src/main.py"], 
        "print('hello')"
    )
    assert decision.decision == "allow"
    
    # Test blocked patch (.env)
    decision = PolicyEngine.evaluate_patch(
        db_session, user_id, repo_id, agent_run_id, 
        [".env", "src/main.py"], 
        "SECRET=123"
    )
    assert decision.decision == "deny"

def test_risk_classification(db_session: Session):
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()
    
    # Low risk
    assessment = RiskClassificationEngine.classify(
        db_session, user_id, repo_id, agent_run_id,
        ["src/utils.py"],
        "def sum(a, b): return a + b"
    )
    assert assessment.risk_level == "low"
    
    # High risk (auth + infra)
    assessment = RiskClassificationEngine.classify(
        db_session, user_id, repo_id, agent_run_id,
        ["src/auth.py", "docker-compose.yml"],
        "login auth password docker"
    )
    assert assessment.risk_level in ["high", "critical"]

def test_security_hardening():
    patch = "subprocess.run('rm -rf /', shell=True)"
    findings = SecurityReviewHardening.analyze_patch(patch)
    assert len(findings) > 0
    assert "Command execution detected" in findings[0]

def test_impact_analysis():
    result = ChangeImpactAnalysis.analyze(["src/auth/login.py", "src/auth/utils.py", "tests/test_auth.py"])
    assert result["affected_files_count"] == 3
    assert len(result["affected_modules"]) == 2

def test_workflow_escalator(db_session: Session):
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()
    
    policy = PolicyEngine.evaluate_patch(db_session, user_id, repo_id, agent_run_id, ["src/main.py"], "print('hello')")
    risk = RiskClassificationEngine.classify(db_session, user_id, repo_id, agent_run_id, ["src/main.py"], "print('hello')")
    
    # High confidence, low risk -> continue
    decision = WorkflowEscalator.evaluate(db_session, user_id, repo_id, agent_run_id, "coding", policy, risk, 0.9)
    assert decision.escalation_result == "continue"
    
    # Low confidence -> review
    decision = WorkflowEscalator.evaluate(db_session, user_id, repo_id, agent_run_id, "coding", policy, risk, 0.4)
    assert decision.escalation_result == "require_review"
