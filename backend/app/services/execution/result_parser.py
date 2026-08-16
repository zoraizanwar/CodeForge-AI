"""
Structured test result parser for CodeForge AI safe execution environment (Step 8).
Parses stdout/stderr from pytest, unittest, Jest/Vitest, and Go test output into standardized summaries.
Never fabricates results.
"""
import re
import logging
from typing import List, Dict, Any
from app.services.execution.command_runner import CommandResult

logger = logging.getLogger("codeforge.execution.parser")


def parse_pytest_output(output: str) -> Dict[str, Any]:
    """Parses pytest summary line (e.g. '21 passed, 2 warnings in 8.84s')."""
    passed = 0
    failed = 0
    skipped = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    skipped_match = re.search(r"(\d+)\s+skipped", output)
    if skipped_match:
        skipped = int(skipped_match.group(1))

    failures = []
    for line in output.splitlines():
        if line.startswith("FAILED ") or line.startswith("FAIL "):
            failures.append(line.strip())

    total = passed + failed + skipped
    return {
        "tests_run": total,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "failures": failures
    }


def parse_unittest_output(output: str) -> Dict[str, Any]:
    """Parses Python unittest output (e.g. 'Ran 5 tests in 0.002s', 'Ran 0 tests in 0.000s')."""
    passed = 0
    failed = 0
    skipped = 0

    run_match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    if run_match:
        total_ran = int(run_match.group(1))

        fail_match = re.search(r"failures=(\d+)", output)
        err_match = re.search(r"errors=(\d+)", output)

        failed_count = (int(fail_match.group(1)) if fail_match else 0) + (int(err_match.group(1)) if err_match else 0)
        failed = failed_count
        passed = max(0, total_ran - failed)
    else:
        return parse_pytest_output(output)

    failures = []
    if failed > 0:
        for line in output.splitlines():
            if line.startswith("FAIL:") or line.startswith("ERROR:"):
                failures.append(line.strip())

    return {
        "tests_run": passed + failed,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "failures": failures
    }


def parse_jest_output(output: str) -> Dict[str, Any]:
    """Parses Jest / Vitest summary (e.g. 'Tests: 2 passed, 2 total')."""
    passed = 0
    failed = 0
    skipped = 0

    passed_match = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output, re.IGNORECASE)
    if failed_match:
        failed = int(failed_match.group(1))

    skipped_match = re.search(r"(\d+)\s+skipped", output, re.IGNORECASE)
    if skipped_match:
        skipped = int(skipped_match.group(1))

    failures = []
    for line in output.splitlines():
        if "FAIL" in line or "error" in line.lower():
            if len(line.strip()) > 3:
                failures.append(line.strip())

    total = passed + failed + skipped
    return {
        "tests_run": total,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "failures": failures
    }


def parse_go_test_output(output: str) -> Dict[str, Any]:
    """Parses Go test output (e.g. '--- FAIL:', '--- PASS:')."""
    passed = len(re.findall(r"--- PASS:", output))
    failed = len(re.findall(r"--- FAIL:", output))

    failures = []
    for line in output.splitlines():
        if line.startswith("--- FAIL:") or line.startswith("FAIL"):
            failures.append(line.strip())

    total = passed + failed
    return {
        "tests_run": total,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": 0,
        "failures": failures
    }


def parse_execution_results(command_results: List[CommandResult]) -> Dict[str, Any]:
    """
    Aggregates command results into a standardized test summary dict.
    """
    total_duration = sum(r.duration_seconds for r in command_results)
    command_strings = [r.command for r in command_results]

    aggregated_run = 0
    aggregated_passed = 0
    aggregated_failed = 0
    aggregated_skipped = 0
    all_failures: List[str] = []

    for res in command_results:
        combined_text = (res.stdout + "\n" + res.stderr).strip()

        # Determine parser type based on command
        if "unittest" in res.command:
            parsed = parse_unittest_output(combined_text)
        elif "pytest" in res.command:
            parsed = parse_pytest_output(combined_text)
        elif "vitest" in res.command or "jest" in res.command or "npm" in res.command:
            parsed = parse_jest_output(combined_text)
        elif "go test" in res.command:
            parsed = parse_go_test_output(combined_text)
        else:
            parsed = {"tests_run": 0, "tests_passed": 0, "tests_failed": 0 if res.exit_code == 0 else 1, "tests_skipped": 0, "failures": []}

        # Check if non-zero exit code was merely due to no tests found
        is_no_tests = (
            parsed["tests_failed"] == 0 and
            ("NO TESTS RAN" in combined_text or "no tests ran" in combined_text.lower() or "0 tests" in combined_text or "no tests found" in combined_text.lower())
        )

        if res.exit_code != 0 and not is_no_tests and res.stderr:
            all_failures.append(f"Command '{res.command}' failed with exit code {res.exit_code}: {res.stderr.strip()[:300]}")

        aggregated_run += parsed["tests_run"]
        aggregated_passed += parsed["tests_passed"]
        aggregated_failed += parsed["tests_failed"]
        aggregated_skipped += parsed["tests_skipped"]
        all_failures.extend(parsed["failures"])

    all_passed = (aggregated_failed == 0) and all(
        r.exit_code == 0 or ("NO TESTS RAN" in (r.stdout + r.stderr) or "no tests ran" in (r.stdout + r.stderr).lower() or "0 tests" in (r.stdout + r.stderr))
        for r in command_results
    )

    return {
        "passed": all_passed,
        "tests_run": aggregated_run,
        "tests_passed": aggregated_passed,
        "tests_failed": aggregated_failed,
        "tests_skipped": aggregated_skipped,
        "duration_seconds": round(total_duration, 2),
        "commands": command_strings,
        "failures": all_failures[:20]  # Cap failure items
    }
