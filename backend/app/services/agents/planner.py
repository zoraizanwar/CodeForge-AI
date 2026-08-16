"""
Planner Agent implementation for CodeForge AI Step 12 Multi-Agent Architecture.
Analyzes user task, repository architecture, symbols, and code chunks to produce a PlanResult.
Does NOT generate code patches.
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.multi_agent import AgentRun, AgentRunStep
from app.services.agents.base import BaseAgent
from app.services.agents.schemas import PlanResult, PlanItem
from app.services.agent.planner import generate_implementation_plan

logger = logging.getLogger("codeforge.agents.planner")


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_type="planner")

    async def execute(
        self,
        db: Session,
        run: AgentRun,
        step: AgentRunStep,
        context: Dict[str, Any]
    ) -> PlanResult:
        logger.info(f"Executing PlannerAgent for run {run.id}...")

        task_desc = context.get("task_description", "")
        from app.providers.ai import get_ai_provider
        from app.services.agent.context_retriever import RetrievedContext
        ai_provider = get_ai_provider()
        retrieved_context = context.get("_retrieved_context")
        if not retrieved_context or not hasattr(retrieved_context, "formatted_context"):
            retrieved_context = RetrievedContext(
                repository_id=context.get("repository", {}).get("id", "test-repo-id"),
                repository_name=context.get("repository", {}).get("name", "test-repo"),
                architecture_summary=context.get("repository_architecture", {}).get("summary", "Python application"),
                frameworks=context.get("repository_architecture", {}).get("frameworks", ["fastapi"]),
                entry_points=context.get("repository_architecture", {}).get("entry_points", ["app/main.py"]),
                dependencies=context.get("dependencies", {}),
                relevant_symbols=context.get("relevant_symbols", []),
                relevant_chunks=context.get("relevant_chunks", []),
                files_analyzed=[],
                formatted_context=f"Repository: {context.get('repository', {}).get('name', 'test-repo')}\nTask: {task_desc}",
                token_count=100
            )

        # Integrate with Step 7 planner logic
        raw_plan = await generate_implementation_plan(ai_provider, task_desc, retrieved_context)

        # Convert to structured PlanResult
        items = []
        target_files = getattr(raw_plan, "target_files", None) or (raw_plan.get("target_files") if isinstance(raw_plan, dict) else ["src/main.py"])
        proposed_changes = getattr(raw_plan, "proposed_changes", None) or (raw_plan.get("proposed_changes") if isinstance(raw_plan, dict) else [])
        task_summary = getattr(raw_plan, "task_summary", None) or (raw_plan.get("task_summary") if isinstance(raw_plan, dict) else f"Implement request: {task_desc}")
        risks = getattr(raw_plan, "compatibility_risks", None) or (raw_plan.get("risks") if isinstance(raw_plan, dict) else ["Requires regression test verification"])
        req_tests = getattr(raw_plan, "required_tests", None) or (raw_plan.get("test_plan") if isinstance(raw_plan, dict) else ["Unit test verification for modified components"])

        for file_path in target_files:
            items.append(PlanItem(
                file_path=file_path,
                action="modify",
                description=f"Implement changes for {task_desc} in {file_path}"
            ))

        plan_result = PlanResult(
            strategy=task_summary,
            affected_files=target_files,
            proposed_changes=items,
            risks=risks if isinstance(risks, list) else [str(risks)],
            required_tests=req_tests if isinstance(req_tests, list) else [str(req_tests)],
            confidence=0.90
        )

        return plan_result
