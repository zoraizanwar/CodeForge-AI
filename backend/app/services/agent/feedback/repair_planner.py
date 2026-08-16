"""
Repair planner for CodeForge AI autonomous feedback loop (Step 10).
Constructs targeted implementation plans to resolve execution test failures.
"""
import json
import logging
from typing import Dict, Any, List
from app.schemas.agent import RootCauseAnalysisSchema
from app.providers.ai import get_ai_provider

logger = logging.getLogger("codeforge.feedback.planner")


class RepairPlanner:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or get_ai_provider()

    async def create_repair_plan(
        self,
        task_description: str,
        analysis: RootCauseAnalysisSchema,
        previous_changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates a targeted repair plan focusing strictly on resolving the root cause.
        """
        system_prompt = (
            "You are CodeForge AI's Repair Planner. "
            "Formulate a minimal, targeted repair plan to fix the execution failure without broad rewrites. "
            "Respond ONLY with a JSON object strictly matching this schema:\n"
            "{\n"
            '  "summary": "Short summary of proposed repair",\n'
            '  "root_cause": "Addressed root cause",\n'
            '  "files_to_modify": ["path/file.py"],\n'
            '  "files_to_create": [],\n'
            '  "files_to_delete": [],\n'
            '  "changes": ["Fix exception handling in file.py"],\n'
            '  "tests_to_validate": ["pytest tests/test_file.py"],\n'
            '  "risks": ["Potential side-effect"]\n'
            "}"
        )

        user_prompt = (
            f"Original Task: {task_description}\n"
            f"Failure Category: {analysis.failure_category}\n"
            f"Root Cause: {analysis.root_cause}\n"
            f"Recommended Fix: {analysis.recommended_fix}\n"
            f"Affected Files: {analysis.affected_files}\n"
            f"Previous Changes: {json.dumps(previous_changes)}\n\n"
            "Plan the minimal corrective repair."
        )

        try:
            resp_str = await self.ai_provider.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2
            )
            clean = resp_str.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            return json.loads(clean.strip())
        except Exception as exc:
            logger.warning(f"Repair plan parsing failed: {exc}. Using fallback plan.")
            return {
                "summary": f"Repair {analysis.failure_category} in {', '.join(analysis.affected_files or ['codebase'])}",
                "root_cause": analysis.root_cause,
                "files_to_modify": analysis.affected_files or [],
                "files_to_create": [],
                "files_to_delete": [],
                "changes": [analysis.recommended_fix],
                "tests_to_validate": [],
                "risks": []
            }
