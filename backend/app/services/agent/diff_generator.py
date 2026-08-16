"""
Unified diff generator for CodeForge AI Agent proposed code changes (Step 7).
"""
import difflib


def generate_unified_diff(
    file_path: str,
    original_content: str,
    proposed_content: str,
    operation: str = "modify"
) -> str:
    """
    Generates a human-readable unified diff string for frontend rendering.
    Supports create, modify, and delete operations.
    """
    if operation == "create":
        orig_lines = []
        prop_lines = proposed_content.splitlines(keepends=True)
        if proposed_content and not proposed_content.endswith("\n"):
            prop_lines[-1] += "\n"
        from_file = "/dev/null"
        to_file = f"b/{file_path}"
    elif operation == "delete":
        orig_lines = original_content.splitlines(keepends=True)
        if original_content and not original_content.endswith("\n"):
            orig_lines[-1] += "\n"
        prop_lines = []
        from_file = f"a/{file_path}"
        to_file = "/dev/null"
    else:  # modify
        orig_lines = original_content.splitlines(keepends=True)
        if original_content and not original_content.endswith("\n"):
            orig_lines[-1] += "\n"
        prop_lines = proposed_content.splitlines(keepends=True)
        if proposed_content and not proposed_content.endswith("\n"):
            prop_lines[-1] += "\n"
        from_file = f"a/{file_path}"
        to_file = f"b/{file_path}"

    diff = difflib.unified_diff(
        orig_lines,
        prop_lines,
        fromfile=from_file,
        tofile=to_file,
        n=3
    )
    return "".join(diff)
