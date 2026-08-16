"""
Failure classifier for CodeForge AI autonomous feedback loop (Step 10).
Parses stdout, stderr, and test summary outputs to extract structured failure metrics.
"""
import re
from typing import Dict, Any, List, Optional


def classify_failure(stdout: str, stderr: str, test_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes execution stdout/stderr streams and test summaries to extract failure metadata.
    Supported ecosystems: Python (pytest/unittest), Node (npm/Jest/Vitest/TypeScript), Go (go test).
    """
    combined_output = (stdout or "") + "\n" + (stderr or "")

    category = "unknown"
    failing_file = None
    line_number = None
    test_name = None
    error_message = ""
    evidence = []

    # 1. Python Pytest / Unittest Patterns
    if "ModuleNotFoundError" in combined_output or "ImportError" in combined_output:
        category = "import_error"
        match = re.search(r"(ModuleNotFoundError|ImportError):\s*(.+)", combined_output)
        if match:
            error_message = match.group(0)
    elif "SyntaxError" in combined_output:
        category = "syntax_error"
        match = re.search(r"File \"([^\"]+)\", line (\d+).*\n\s*(SyntaxError:\s*.+)", combined_output)
        if match:
            failing_file, line_number, error_message = match.group(1), int(match.group(2)), match.group(3)
    elif "AssertionError" in combined_output or "FAILED " in combined_output:
        category = "assertion_failure"
        match = re.search(r"FAILED\s+([^\s:]+)(?:::([^\s]+))?", combined_output)
        if match:
            failing_file = match.group(1)
            test_name = match.group(2)
        assert_match = re.search(r"E\s+(AssertionError:\s*.+)", combined_output)
        if assert_match:
            error_message = assert_match.group(1)
    elif "TypeError" in combined_output:
        category = "type_error"
        match = re.search(r"TypeError:\s*.+", combined_output)
        if match:
            error_message = match.group(0)

    # 2. Node / TypeScript / Jest / Vitest Patterns
    elif "TS" in combined_output and ("error TS" in combined_output or "TypeScript" in combined_output):
        category = "type_error"
        match = re.search(r"([^\s()]+\.[jt]sx?)\((\d+),\d+\):\s*error\s*(TS\d+:\s*.+)", combined_output)
        if match:
            failing_file, line_number, error_message = match.group(1), int(match.group(2)), match.group(3)
    elif "Cannot find module" in combined_output:
        category = "import_error"
        match = re.search(r"Cannot find module '([^']+)'", combined_output)
        if match:
            error_message = f"Cannot find module '{match.group(1)}'"
    elif "FAIL " in combined_output or "Jest" in combined_output or "vitest" in combined_output:
        category = "test_failure"
        match = re.search(r"FAIL\s+([^\s]+)", combined_output)
        if match:
            failing_file = match.group(1)

    # 3. Go test / compilation patterns
    elif "go test" in combined_output or "FAIL:" in combined_output:
        category = "test_failure"
        match = re.search(r"--- FAIL:\s+([^\s]+)\s+\((.+)\)", combined_output)
        if match:
            test_name = match.group(1)
        file_match = re.search(r"([^\s:]+_test\.go):(\d+):", combined_output)
        if file_match:
            failing_file, line_number = file_match.group(1), int(file_match.group(2))

    # Extract sample evidence lines
    lines = [l.strip() for l in combined_output.split("\n") if l.strip()]
    for line in lines:
        if any(kw in line for kw in ["FAIL", "ERROR", "Error:", "FAILED", "AssertionError", "SyntaxError", "TypeError"]):
            evidence.append(line[:200])
            if len(evidence) >= 5:
                break

    if not error_message and evidence:
        error_message = evidence[0]

    return {
        "failure_category": category,
        "failing_file": failing_file,
        "line_number": line_number,
        "test_name": test_name,
        "error_message": error_message or "Execution failed during automated testing.",
        "evidence": evidence
    }
