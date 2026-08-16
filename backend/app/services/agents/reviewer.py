"""
Reviewer Agent implementation for CodeForge AI Step 12 Multi-Agent Architecture.
Independently inspects generated code changes and produces structured ReviewResult with findings.
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.multi_agent import AgentRun, AgentRunStep
from app.services.agents.base import BaseAgent
from app.services.agents.schemas import ReviewResult, ReviewFinding

logger = logging.getLogger("codeforge.agents.reviewer")


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_type="reviewer")

    async def execute(
        self,
        db: Session,
        run: AgentRun,
        step: AgentRunStep,
        context: Dict[str, Any]
    ) -> ReviewResult:
        logger.info(f"Executing ReviewerAgent for run {run.id}...")

        engineer_output = context.get("previous_outputs", {}).get("engineer", {})
        file_ops = engineer_output.get("file_operations", [])

        findings: List[ReviewFinding] = []
        has_critical = False

        for op in file_ops:
            path = op.get("file_path", "")
            content = op.get("content", "") or ""

            # Standardized code quality analysis checks
            if "TODO" in content or "FIXME" in content:
                findings.append(ReviewFinding(
                    file=path,
                    line=1,
                    category="maintainability",
                    severity="info",
                    description="Contains unresolved TODO/FIXME markers.",
                    recommendation="Address or track outstanding TODOs before merging."
                ))

            if "eval(" in content or "exec(" in content:
                has_critical = True
                findings.append(ReviewFinding(
                    file=path,
                    line=1,
                    category="security",
                    severity="critical",
                    description="Dynamic execution function (eval/exec) detected.",
                    recommendation="Remove dynamic code execution calls immediately."
                ))

            if "except Exception:" in content and "pass" in content:
                findings.append(ReviewFinding(
                    file=path,
                    line=1,
                    category="correctness",
                    severity="medium",
                    description="Silent exception swallowing detected (`except: pass`).",
                    recommendation="Explicitly catch and log or handle exception."
                ))

        approved = not has_critical
        confidence = 0.92 if approved else 0.70

        return ReviewResult(
            findings=findings,
            approved=approved,
            summary="Review completed. Code meets maintainability standards." if approved else "Review identified critical findings requiring resolution.",
            confidence=confidence
        )
