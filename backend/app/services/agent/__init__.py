"""
CodeForge AI Agent services package (Step 7).
"""
from app.services.agent.diff_generator import generate_unified_diff
from app.services.agent.validator import validate_proposed_changes, validate_proposed_change, ChangeValidationError
from app.services.agent.context_retriever import retrieve_task_context, RetrievedContext
from app.services.agent.planner import generate_implementation_plan
from app.services.agent.code_generator import generate_code_changes
from app.services.agent.orchestrator import run_agent_task_pipeline

__all__ = [
    "generate_unified_diff",
    "validate_proposed_changes",
    "validate_proposed_change",
    "ChangeValidationError",
    "retrieve_task_context",
    "RetrievedContext",
    "generate_implementation_plan",
    "generate_code_changes",
    "run_agent_task_pipeline"
]
