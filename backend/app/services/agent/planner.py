"""
Implementation planner service for CodeForge AI Agent (Step 7).
Generates a structured implementation plan from user task requirements and retrieved repository context.
"""
import logging
from typing import Optional
from app.providers.ai.base import AIProvider
from app.schemas.agent import ImplementationPlanSchema
from app.services.agent.context_retriever import RetrievedContext

logger = logging.getLogger("codeforge.agent.planner")

PLANNING_SYSTEM_PROMPT = (
    "You are an expert AI software architect and engineering planner. "
    "Analyze the provided repository context and user task request, and formulate a clear, "
    "structured implementation plan. Break down the task into precise file changes, affected dependencies, "
    "implementation steps, required tests, and potential architectural or compatibility risks."
)


async def generate_implementation_plan(
    ai_provider: AIProvider,
    task_description: str,
    context: RetrievedContext
) -> ImplementationPlanSchema:
    """
    Generates a structured implementation plan using the AI provider.
    Falls back to a deterministic structured plan if provider fails or is mocked.
    """
    prompt = (
        f"USER TASK: {task_description}\n\n"
        f"REPOSITORY CONTEXT:\n{context.formatted_context}\n\n"
        "Create a comprehensive implementation plan for executing this task."
    )

    try:
        plan = await ai_provider.generate_structured_output(
            prompt=prompt,
            response_model=ImplementationPlanSchema,
            system_prompt=PLANNING_SYSTEM_PROMPT
        )

        # Validate that essential fields are populated; fallback if AI returned empty default
        if plan and (plan.task_summary or plan.proposed_changes):
            return plan

    except Exception as e:
        logger.warning(f"AI Provider plan generation failed/mocked: {str(e)}. Using fallback generator.")

    # Deterministic fallback planner
    relevant_files = context.files_analyzed if context.files_analyzed else ["main.py"]
    symbol_names = [s["name"] for s in context.relevant_symbols[:5]]

    return ImplementationPlanSchema(
        task_summary=f"Implementation plan for: {task_description}",
        architecture_understanding=(
            f"Repository '{context.repository_name}' uses {', '.join(context.frameworks) if context.frameworks else 'standard architecture'}. "
            f"Main entry points: {', '.join(context.entry_points) if context.entry_points else 'detected files'}."
        ),
        relevant_files=relevant_files,
        relevant_symbols=symbol_names,
        proposed_changes=[
            f"Implement changes for '{task_description}' across relevant files: {', '.join(relevant_files[:3])}.",
            "Add validation and unit tests to ensure functional stability."
        ],
        dependencies_affected=list(context.dependencies.keys())[:3],
        tests=[
            f"Add unit tests covering proposed functionality in {relevant_files[0]}",
            "Verify complete backend API test suite pass"
        ],
        implementation_order=[
            "1. Inspect existing file signatures and dependencies",
            "2. Apply proposed file modifications / creations",
            "3. Run automated tests and verify security bounds"
        ],
        risks=[
            "Ensure no breaking changes to existing API contracts",
            "Maintain strict tenant isolation and path boundary checks"
        ]
    )
