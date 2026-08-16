"""
Repair generator for CodeForge AI autonomous feedback loop (Step 10).
Synthesizes updated code operations (create, modify, delete) to resolve execution errors.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from app.schemas.agent import FileChangeSchema, ImplementationPlanSchema
from app.providers.ai import get_ai_provider
from app.services.agent.code_generator import generate_code_changes
from app.services.agent.context_retriever import RetrievedContext
from app.services.agent.diff_generator import generate_unified_diff

logger = logging.getLogger("codeforge.feedback.generator")


class RepairGenerator:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or get_ai_provider()

    async def generate_repair_patch(
        self,
        task_description: str,
        repair_plan: Dict[str, Any],
        root_cause_analysis: Dict[str, Any],
        previous_changes: List[Dict[str, Any]],
        file_contents: Dict[str, str]
    ) -> List[FileChangeSchema]:
        """
        Generates updated code file operations to resolve the failure.
        """
        plan_schema = ImplementationPlanSchema(
            task_summary=repair_plan.get("summary", "Targeted repair"),
            architecture_understanding=root_cause_analysis.get("root_cause", ""),
            relevant_files=repair_plan.get("files_to_modify", []),
            proposed_changes=repair_plan.get("changes", []),
            tests=repair_plan.get("tests_to_validate", []),
            risks=repair_plan.get("risks", [])
        )

        formatted_source = "\n\n".join(f"=== FILE: {k} ===\n{v}" for k, v in file_contents.items())
        dummy_context = RetrievedContext(
            repository_id="repair",
            repository_name="repair_repo",
            architecture_summary="Repair context",
            frameworks=[],
            entry_points=[],
            dependencies={},
            relevant_symbols=[],
            relevant_chunks=[],
            files_analyzed=list(file_contents.keys()),
            formatted_context=formatted_source,
            token_count=100
        )

        resp = await generate_code_changes(
            ai_provider=self.ai_provider,
            repo_local_path=".",
            task_description=f"REPAIR: {task_description}. Fix root cause: {root_cause_analysis.get('root_cause', '')}",
            plan=plan_schema,
            context=dummy_context
        )

        # Enhance file changes with diff previews
        processed_changes = []
        for change in resp.changes:
            orig = file_contents.get(change.file_path, "")
            diff_text = generate_unified_diff(
                file_path=change.file_path,
                original_content=orig if change.operation != "create" else None,
                proposed_content=change.proposed_content if change.operation != "delete" else ""
            )
            change.diff = diff_text
            processed_changes.append(change)

        return processed_changes
