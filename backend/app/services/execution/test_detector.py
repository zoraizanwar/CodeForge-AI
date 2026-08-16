"""
Project & test framework detector for CodeForge AI safe execution environment (Step 8).
Inspects workspace files to safely discover Python, Node.js, and Go test/build commands.
Only produces trusted, predefined safe commands.
"""
import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ProjectTestConfig:
    language: str  # python, node, go, unknown
    package_manager: Optional[str] = None
    manifest_file: Optional[str] = None
    prep_commands: List[List[str]] = field(default_factory=list)
    test_commands: List[List[str]] = field(default_factory=list)
    lint_commands: List[List[str]] = field(default_factory=list)


def detect_project_and_test_commands(workspace_path: str) -> ProjectTestConfig:
    """
    Inspects files in workspace to detect language ecosystem and build trusted command sequences.
    Never accepts arbitrary user-supplied commands.
    """
    if not os.path.exists(workspace_path):
        return ProjectTestConfig(language="unknown")

    files = set(os.listdir(workspace_path))

    # 1. Python Detection
    if any(f in files for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")) or any(f.endswith(".py") for f in files):
        prep_cmds: List[List[str]] = []
        test_cmds: List[List[str]] = []
        lint_cmds: List[List[str]] = []

        # Dependency installation (use venv or python -m pip if requirements.txt exists)
        # Note: sys.executable is used for local isolation when available
        import sys
        python_bin = sys.executable or "python"

        # Check for pytest or test files
        has_pytest = False
        if "pyproject.toml" in files:
            try:
                with open(os.path.join(workspace_path, "pyproject.toml"), "r", encoding="utf-8") as f:
                    content = f.read()
                    if "pytest" in content:
                        has_pytest = True
            except Exception:
                pass

        if "requirements.txt" in files:
            try:
                with open(os.path.join(workspace_path, "requirements.txt"), "r", encoding="utf-8") as f:
                    content = f.read()
                    if "pytest" in content:
                        has_pytest = True
            except Exception:
                pass

        # Also check for tests directory
        tests_dir_exists = os.path.exists(os.path.join(workspace_path, "tests")) or os.path.exists(os.path.join(workspace_path, "test"))

        if has_pytest or tests_dir_exists:
            test_cmds.append([python_bin, "-m", "pytest"])
        else:
            test_cmds.append([python_bin, "-m", "unittest", "discover"])

        return ProjectTestConfig(
            language="python",
            package_manager="pip",
            manifest_file="pyproject.toml" if "pyproject.toml" in files else ("requirements.txt" if "requirements.txt" in files else None),
            prep_commands=prep_cmds,
            test_commands=test_cmds,
            lint_commands=lint_cmds
        )

    # 2. Node.js / JavaScript / TypeScript Detection
    if "package.json" in files:
        prep_cmds = []
        test_cmds = []
        lint_cmds = []

        try:
            pkg_path = os.path.join(workspace_path, "package.json")
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
                scripts = pkg_data.get("scripts", {})

                # Node npm test command
                if "test" in scripts:
                    test_cmds.append(["npm", "test"])
                elif "vitest" in pkg_data.get("devDependencies", {}) or "vitest" in pkg_data.get("dependencies", {}):
                    test_cmds.append(["npx", "vitest", "run"])
                elif "jest" in pkg_data.get("devDependencies", {}) or "jest" in pkg_data.get("dependencies", {}):
                    test_cmds.append(["npx", "jest"])
                else:
                    test_cmds.append(["npm", "test"])

                if "build" in scripts:
                    lint_cmds.append(["npm", "run", "build"])
        except Exception:
            test_cmds.append(["npm", "test"])

        return ProjectTestConfig(
            language="node",
            package_manager="npm",
            manifest_file="package.json",
            prep_commands=prep_cmds,
            test_commands=test_cmds,
            lint_commands=lint_cmds
        )

    # 3. Go Detection
    if "go.mod" in files or any(f.endswith(".go") for f in files):
        return ProjectTestConfig(
            language="go",
            package_manager="go",
            manifest_file="go.mod" if "go.mod" in files else None,
            prep_commands=[],
            test_commands=[["go", "test", "./..."]],
            lint_commands=[["go", "vet", "./..."]]
        )

    return ProjectTestConfig(language="unknown")
