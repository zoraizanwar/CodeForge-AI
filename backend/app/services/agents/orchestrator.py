"""
Orchestrator Agent for CodeForge AI Step 12 Multi-Agent Architecture.
Coordinates specialized agents (Planner -> Engineer -> Reviewer -> Security -> Tester -> Repair)
through Step 11 durable jobs with confidence-based escalation and mandatory human approval gates.
"""
import uuid
import datetime
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.multi_agent import AgentRun, AgentRunStep
from app.models.agent import AgentTask
from app.services.agents.base import BaseAgent
from app.services.agents.schemas import AgentDecision, WorkflowResult
from app.services.agents.context import build_agent_context
from app.services.agents.planner import PlannerAgent
from app.services.agents.engineer import EngineerAgent
from app.services.agents.reviewer import ReviewerAgent
from app.services.agents.security import SecurityAgent
from app.services.agents.tester import TesterAgent
from app.services.agents.repair import RepairAgent

logger = logging.getLogger("codeforge.agents.orchestrator")


async def run_multi_agent_workflow(run_id: uuid.UUID, db: Session) -> WorkflowResult:
    """
    Executes or advances a durable Multi-Agent Workflow run.
    Evaluates confidence thresholds and enforces human approval gates before PR creation.
    """
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise ValueError(f"AgentRun {run_id} not found.")

    if run.status in ["cancelled", "completed", "rejected"]:
        return WorkflowResult(
            run_id=str(run.id),
            status=run.status,
            overall_progress=run.overall_progress,
            error_message=run.error_message
        )

    run.status = "running"
    if not run.started_at:
        run.started_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    # Agent map
    agents: Dict[str, BaseAgent] = {
        "planner": PlannerAgent(),
        "engineer": EngineerAgent(),
        "reviewer": ReviewerAgent(),
        "security": SecurityAgent(),
        "tester": TesterAgent(),
        "repair": RepairAgent(),
    }

    workflow_sequence = ["planner", "engineer", "reviewer", "security", "tester"]

    try:
        for stage in workflow_sequence:
            # Check for cancellation
            db.refresh(run)
            if run.status == "cancelled":
                logger.warning(f"Run {run.id} was cancelled during execution.")
                return WorkflowResult(run_id=str(run.id), status="cancelled", overall_progress=run.overall_progress)

            run.current_agent = stage
            run.workflow_stage = stage
            run.overall_progress = min(90, (workflow_sequence.index(stage) + 1) * 18)
            db.commit()

            # Create or fetch step
            step = db.query(AgentRunStep).filter(
                AgentRunStep.run_id == run.id,
                AgentRunStep.agent_type == stage,
                AgentRunStep.status.in_(["pending", "running"])
            ).first()

            if not step:
                step = AgentRunStep(
                    id=uuid.uuid4(),
                    run_id=run.id,
                    agent_type=stage,
                    status="running",
                    started_at=datetime.datetime.now(datetime.timezone.utc)
                )
                db.add(step)
                db.commit()
                db.refresh(step)

            # Build context & execute
            ctx = build_agent_context(db, run, stage, previous_steps=run.steps)
            step.input_context = ctx
            db.commit()

            agent = agents[stage]
            res = await agent.execute(db, run, step, ctx)
            res_dict = res.model_dump(mode="json") if hasattr(res, "model_dump") else res

            step.output = res_dict
            step.confidence = getattr(res, "confidence", 0.90)
            step.completed_at = datetime.datetime.now(datetime.timezone.utc)

            # Stage specific checks & confidence escalation
            conf = step.confidence

            if stage == "planner":
                if conf < settings.AGENT_MIN_CONFIDENCE:
                    run.status = "human_review_required"
                    step.status = "review_needed"
                    db.commit()
                    return WorkflowResult(run_id=str(run.id), status="human_review_required", overall_progress=run.overall_progress)
                step.status = "passed"

            elif stage == "engineer":
                if conf < settings.AGENT_MIN_CONFIDENCE:
                    run.status = "human_review_required"
                    step.status = "review_needed"
                    db.commit()
                    return WorkflowResult(run_id=str(run.id), status="human_review_required", overall_progress=run.overall_progress)
                step.status = "passed"

            elif stage == "reviewer":
                approved = res_dict.get("approved", False)
                if not approved or conf < settings.AGENT_REVIEW_THRESHOLD:
                    step.status = "review_needed"
                else:
                    step.status = "passed"

            elif stage == "security":
                passed = res_dict.get("passed", False)
                has_crit = res_dict.get("has_critical_or_high", False)
                if has_crit or not passed or conf < settings.AGENT_SECURITY_THRESHOLD:
                    step.status = "failed"
                    run.status = "human_review_required"
                    run.error_message = "Security reviewer identified critical or high findings requiring human review."
                    db.commit()
                    return WorkflowResult(
                        run_id=str(run.id),
                        status="human_review_required",
                        overall_progress=run.overall_progress,
                        error_message=run.error_message
                    )
                step.status = "passed"

            elif stage == "tester":
                passed = res_dict.get("passed", False)
                if not passed:
                    step.status = "failed"

                    # Trigger Repair Agent if repair iterations permitted
                    repair_step = AgentRunStep(
                        id=uuid.uuid4(),
                        run_id=run.id,
                        agent_type="repair",
                        status="running",
                        started_at=datetime.datetime.now(datetime.timezone.utc)
                    )
                    db.add(repair_step)
                    db.commit()
                    db.refresh(repair_step)

                    try:
                        repair_res = await agents["repair"].execute(db, run, repair_step, ctx)
                        repair_dict = repair_res.model_dump(mode="json") if hasattr(repair_res, "model_dump") else repair_res
                        repair_step.output = repair_dict
                        repair_step.confidence = repair_res.confidence
                        repair_step.completed_at = datetime.datetime.now(datetime.timezone.utc)

                        if repair_res.tests_passed and repair_res.confidence >= settings.AGENT_REPAIR_THRESHOLD:
                            repair_step.status = "passed"
                        else:
                            repair_step.status = "review_needed"
                            run.status = "human_review_required"
                            run.error_message = "Repair iteration requires human review or failed test resolution."
                            db.commit()
                            return WorkflowResult(run_id=str(run.id), status="human_review_required", overall_progress=run.overall_progress)
                    except Exception as rep_err:
                        repair_step.status = "failed"
                        repair_step.error_message = str(rep_err)
                        run.status = "human_review_required"
                        db.commit()
                        return WorkflowResult(run_id=str(run.id), status="human_review_required", overall_progress=run.overall_progress)
                else:
                    step.status = "passed"

            db.commit()

        # All automated stages passed successfully -> Require explicit Human Approval Gate before PR creation
        run.status = "human_review_required"
        run.workflow_stage = "human_approval_gate"
        run.overall_progress = 95
        run.final_decision = {
            "decision": "human_review_required",
            "reason": "All automated agent checks passed (Plan, Engineer, Reviewer, Security, Tester). Human approval required before PR creation.",
            "next_agent": None,
            "confidence": 0.95
        }
        db.commit()

        return WorkflowResult(
            run_id=str(run.id),
            status="human_review_required",
            overall_progress=95,
            final_decision=AgentDecision(**run.final_decision)
        )

    except Exception as exc:
        logger.error(f"Multi-agent workflow failed for run {run.id}: {exc}", exc_info=True)
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        return WorkflowResult(run_id=str(run.id), status="failed", overall_progress=run.overall_progress, error_message=str(exc))
