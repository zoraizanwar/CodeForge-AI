"""
Repair Agent implementation for CodeForge AI Step 12 Multi-Agent Architecture.
Consumes test & review findings, generates minimal targeted repairs via Step 10 repair loop,
and validates in Step 8 sandbox (max 3 iterations).
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.multi_agent import AgentRun, AgentRunStep
from app.services.agents.base import BaseAgent
from app.services.agents.schemas import RepairResult, FileOperation
from app.services.agent.feedback.repair_orchestrator import execute_repair_loop

logger = logging.getLogger("codeforge.agents.repair")

MAX_REPAIR_ITERATIONS = 3


class RepairAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_type="repair")

    async def execute(
        self,
        db: Session,
        run: AgentRun,
        step: AgentRunStep,
        context: Dict[str, Any]
    ) -> RepairResult:
        logger.info(f"Executing RepairAgent for run {run.id}...")

        previous_outputs = context.get("previous_outputs", {})
        test_output = previous_outputs.get("tester", {})
        review_output = previous_outputs.get("reviewer", {})
        security_output = previous_outputs.get("security", {})

        # Count repair attempts in this run
        existing_repair_steps = [s for s in run.steps if s.agent_type == "repair" and s.status in ["passed", "failed"]]
        iteration = len(existing_repair_steps) + 1

        if iteration > MAX_REPAIR_ITERATIONS:
            raise ValueError(f"Maximum repair iteration limit ({MAX_REPAIR_ITERATIONS}) reached. Human intervention required.")

        task_id = run.task_id
        if not task_id:
            raise ValueError("RepairAgent requires a valid task_id.")

        # Trigger Step 10 repair loop
        repair_iteration = await execute_repair_loop(task_id, db=db)

        passed = repair_iteration.test_passed if repair_iteration else False
        root_cause = repair_iteration.error_analysis.get("likely_cause", "Unresolved test/review failure") if repair_iteration else "Unknown failure"

        repair_ops: List[FileOperation] = []
        if repair_iteration and repair_iteration.repaired_patch:
            for op in repair_iteration.repaired_patch:
                repair_ops.append(FileOperation(
                    file_path=op.get("file_path", ""),
                    action=op.get("action", "modify"),
                    content=op.get("content", ""),
                    patch_diff=op.get("patch_diff", "")
                ))

        confidence = 0.85 if passed else 0.60

        return RepairResult(
            iteration_number=iteration,
            root_cause=root_cause,
            repair_patch=repair_ops,
            tests_passed=passed,
            confidence=confidence
        )
