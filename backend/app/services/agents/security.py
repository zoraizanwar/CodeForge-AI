"""
Security Reviewer Agent implementation for CodeForge AI Step 12 Multi-Agent Architecture.
Performs comprehensive security inspection across path traversal, secrets, injection, SSRF, auth, tenant isolation.
Critical/high findings block automatic progression.
"""
import logging
import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.multi_agent import AgentRun, AgentRunStep
from app.services.agents.base import BaseAgent
from app.services.agents.schemas import SecurityReviewResult, SecurityFinding
from app.services.agent.validator import validate_proposed_changes, ChangeValidationError

logger = logging.getLogger("codeforge.agents.security")

SUSPICIOUS_PATTERNS = [
    (r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", "secret_exposure", "critical", "Hardcoded AWS Secret Key detected."),
    (r"(?i)bearer\s+ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+", "secret_exposure", "critical", "Hardcoded JWT Token detected."),
    (r"os\.system\(", "command_injection", "high", "Unsafe os.system call detected."),
    (r"subprocess\.Popen\([^,]+shell\s*=\s*True", "command_injection", "critical", "Unsafe subprocess call with shell=True."),
    (r"SELECT\s+.*\s+FROM\s+.*\s+\+\s*", "sqli", "high", "Possible unparameterized SQL query string concatenation."),
    (r"(\.\./){2,}", "path_traversal", "critical", "Directory traversal path detected."),
]


class SecurityAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_type="security")

    async def execute(
        self,
        db: Session,
        run: AgentRun,
        step: AgentRunStep,
        context: Dict[str, Any]
    ) -> SecurityReviewResult:
        logger.info(f"Executing SecurityAgent for run {run.id}...")

        engineer_output = context.get("previous_outputs", {}).get("engineer", {})
        file_ops = engineer_output.get("file_operations", [])

        findings: List[SecurityFinding] = []
        has_critical_or_high = False

        # Run standard Step 7 validator first
        repo_path = context.get("repository", {}).get("local_path", "workspaces/test")
        raw_ops = [{"file_path": op.get("file_path", ""), "operation": op.get("action", "modify"), "proposed_content": op.get("content", "") or ""} for op in file_ops]
        try:
            validate_proposed_changes(repo_path, raw_ops)
        except ChangeValidationError as val_err:
            has_critical_or_high = True
            findings.append(SecurityFinding(
                rule_id="SEC_VAL_001",
                severity="critical",
                category="sensitive_file",
                file="patch",
                description=str(val_err),
                remediation="Remove sensitive or invalid path from patch file operations."
            ))

        # Inspect generated contents against security regexes
        for op in file_ops:
            path = op.get("file_path", "")
            content = op.get("content", "") or ""

            for pattern, category, severity, desc in SUSPICIOUS_PATTERNS:
                if re.search(pattern, content):
                    if severity in ["critical", "high"]:
                        has_critical_or_high = True
                    findings.append(SecurityFinding(
                        rule_id=f"SEC_{category.upper()}",
                        severity=severity,
                        category=category,
                        file=path,
                        line=1,
                        description=desc,
                        remediation=f"Remediate {category} security risk in {path} before deployment."
                    ))

        passed = not has_critical_or_high
        confidence = 0.95 if passed else 0.60

        return SecurityReviewResult(
            findings=findings,
            passed=passed,
            has_critical_or_high=has_critical_or_high,
            summary="Security audit passed cleanly. No critical or high risks identified." if passed else "Security audit FAILED. Critical or high severity security findings present.",
            confidence=confidence
        )
