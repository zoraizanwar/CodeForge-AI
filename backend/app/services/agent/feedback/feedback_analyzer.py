"""
Feedback analyzer for CodeForge AI autonomous bug fixing (Step 10).
Analyzes execution tracebacks and queries the LLM engine to extract root causes.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from app.schemas.agent import RootCauseAnalysisSchema
from app.services.agent.feedback.failure_classifier import classify_failure
from app.providers.ai import get_ai_provider

logger = logging.getLogger("codeforge.feedback.analyzer")


class FeedbackAnalyzer:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or get_ai_provider()

    async def analyze_execution_failure(
        self,
        task_description: str,
        stdout: str,
        stderr: str,
        test_summary: Optional[Dict[str, Any]],
        previous_changes: List[Dict[str, Any]]
    ) -> RootCauseAnalysisSchema:
        """
        Extracts failure metrics and queries the AI engine for a structured root cause hypothesis.
        """
        classified = classify_failure(stdout, stderr, test_summary)

        system_prompt = (
            "You are CodeForge AI's Expert Root Cause Diagnostic Engine. "
            "Analyze software execution tracebacks, test failures, and generated patches. "
            "Respond ONLY with a JSON object strictly matching this schema:\n"
            "{\n"
            '  "failure_category": "syntax_error|type_error|import_error|dependency_error|test_failure|assertion_failure|runtime_error|build_error|lint_error|unknown",\n'
            '  "root_cause": "Detailed technical explanation of why the test failed",\n'
            '  "confidence": 0.95,\n'
            '  "affected_files": ["path/to/file.py"],\n'
            '  "affected_symbols": ["symbol_name"],\n'
            '  "evidence": ["Exact error traceback line"],\n'
            '  "recommended_fix": "Description of corrective patch to apply",\n'
            '  "requires_dependency_change": false\n'
            "}"
        )

        user_prompt = (
            f"Original Request: {task_description}\n\n"
            f"Heuristic Category: {classified['failure_category']}\n"
            f"Failing File: {classified['failing_file'] or 'Unknown'}\n"
            f"Line Number: {classified['line_number'] or 'N/A'}\n"
            f"Error Message: {classified['error_message']}\n"
            f"Evidence: {json.dumps(classified['evidence'])}\n\n"
            f"Previous Patch Changes: {json.dumps(previous_changes)}\n\n"
            f"Execution Stdout:\n{stdout[:1500]}\n\n"
            f"Execution Stderr:\n{stderr[:1500]}\n\n"
            "Construct a precise root cause analysis."
        )

        try:
            resp_str = await self.ai_provider.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )

            # Strip potential markdown fence wrappers
            clean_json = resp_str.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json)
            return RootCauseAnalysisSchema(
                failure_category=parsed.get("failure_category", classified["failure_category"]),
                root_cause=parsed.get("root_cause", classified["error_message"]),
                confidence=float(parsed.get("confidence", 0.9)),
                affected_files=parsed.get("affected_files") or ([classified["failing_file"]] if classified["failing_file"] else []),
                affected_symbols=parsed.get("affected_symbols", []),
                evidence=parsed.get("evidence", classified["evidence"]),
                recommended_fix=parsed.get("recommended_fix", "Apply targeted repair patch."),
                requires_dependency_change=bool(parsed.get("requires_dependency_change", False))
            )
        except Exception as exc:
            logger.warning(f"AI root cause analysis parsing failed: {exc}. Falling back to heuristic classification.")
            return RootCauseAnalysisSchema(
                failure_category=classified["failure_category"],
                root_cause=classified["error_message"],
                confidence=0.8,
                affected_files=[classified["failing_file"]] if classified["failing_file"] else [],
                affected_symbols=[],
                evidence=classified["evidence"],
                recommended_fix="Fix identified test assertion / runtime failure.",
                requires_dependency_change=False
            )
