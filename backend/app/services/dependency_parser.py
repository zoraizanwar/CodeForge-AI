"""
Dependency file parser for CodeForge AI repository intelligence (Step 6).

Parses common dependency manifests:
  - requirements.txt
  - pyproject.toml
  - Pipfile
  - package.json
  - package-lock.json (just extract name)
  - yarn.lock (just extract packages)
  - Cargo.toml
  - go.mod

Returns a normalized dict: {package_name: version_or_"unknown"}

Also detects frameworks based on actual dependency presence:
  - FastAPI, Django, Flask: from Python deps
  - React, Next.js, Vue, Angular: from JS deps
  - Express, Node.js: from JS deps
  - Go web frameworks: from go.mod

Never falsely detects frameworks from filenames alone.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEPENDENCY_FILENAMES: frozenset[str] = frozenset(
    {
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "Cargo.toml",
        "go.mod",
    }
)

# Regex for version specifiers in requirements.txt lines
_REQ_VERSION_RE = re.compile(
    r"^([A-Za-z0-9_\-\.]+)\s*(?:==|>=|<=|~=|!=|>|<)?\s*(.*)?$"
)

# Supported version operator prefixes (for stripping from version strings)
_VERSION_OPS = ("==", ">=", "<=", "~=", "!=", ">", "<")


# ---------------------------------------------------------------------------
# Individual parsers
# ---------------------------------------------------------------------------


def parse_requirements_txt(content: str) -> Dict[str, str]:
    """
    Parse a pip *requirements.txt* file.

    Skips blank lines, comments (``#``), and option flags (``-r``, ``-c``, …).
    Handles ``==``, ``>=``, ``<=``, ``~=``, ``!=`` specifiers and lines with
    no version constraint at all.

    Returns:
        ``{package_name: version}`` — version is ``"unknown"`` when absent.
    """
    deps: Dict[str, str] = {}
    try:
        for raw_line in content.splitlines():
            line = raw_line.strip()
            # Skip blank lines, comments, and option flags
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Strip inline comment
            line = line.split("#")[0].strip()
            if not line:
                continue
            # Strip environment markers (e.g., `; python_version >= "3.8"`)
            line = line.split(";")[0].strip()
            # Extract package name and optional version
            m = re.match(
                r"^([A-Za-z0-9_\-\.]+)\s*(?:(==|>=|<=|~=|!=|>|<)\s*([\S]+))?",
                line,
            )
            if m:
                name = m.group(1).lower()
                version = m.group(3) if m.group(3) else "unknown"
                deps[name] = version
    except Exception:
        logger.exception("parse_requirements_txt: failed to parse content.")
    return deps


def parse_pyproject_toml(content: str) -> Dict[str, str]:
    """
    Parse ``[project] dependencies`` and ``[tool.poetry.dependencies]`` from a
    *pyproject.toml* file using regex and string parsing (no external library).

    Returns:
        ``{package_name: version}``
    """
    deps: Dict[str, str] = {}
    try:
        lines = content.splitlines()
        in_section: str = ""
        # We collect lines that belong to a dependencies list/table
        collecting_list = False  # inside a TOML inline/block array

        for raw in lines:
            line = raw.strip()

            # Detect section headers
            if re.match(r"^\[tool\.poetry\.dependencies\]", line):
                in_section = "poetry"
                collecting_list = False
                continue
            if re.match(r"^\[project\]", line):
                in_section = "project"
                collecting_list = False
                continue
            if re.match(r"^\[", line):
                # Check if we are entering a sub-section of [project]
                if re.match(r"^\[project\.", line):
                    # sub-table of project, keep watching for dependencies key
                    in_section = "project_sub"
                elif in_section in ("project", "project_sub") and re.match(
                    r"^\[project\.optional-dependencies\]", line
                ):
                    in_section = "project_opt"
                else:
                    in_section = ""
                collecting_list = False
                continue

            if in_section == "poetry":
                # Poetry uses `package = "version"` or `package = {version = "..."}`
                m = re.match(r'^([A-Za-z0-9_\-\.]+)\s*=\s*"([^"]*)"', line)
                if m:
                    name = m.group(1).lower()
                    if name == "python":
                        continue
                    deps[name] = m.group(2)
                    continue
                # Dict-style: package = {version = "..."}
                m2 = re.match(r'^([A-Za-z0-9_\-\.]+)\s*=\s*\{.*version\s*=\s*"([^"]*)"', line)
                if m2:
                    name = m2.group(1).lower()
                    if name != "python":
                        deps[name] = m2.group(2)

            elif in_section in ("project", "project_sub", "project_opt"):
                # PEP 517 style: dependencies = ["pkg>=1.0", ...]
                if re.match(r"^dependencies\s*=\s*\[", line):
                    collecting_list = True
                    # Parse inline items on the same line
                    inner = re.sub(r"^dependencies\s*=\s*\[", "", line).rstrip("]")
                    _extract_pep517_deps(inner, deps)
                    if "]" in line:
                        collecting_list = False
                    continue
                if collecting_list:
                    if "]" in line:
                        _extract_pep517_deps(line.rstrip("]"), deps)
                        collecting_list = False
                    else:
                        _extract_pep517_deps(line, deps)
    except Exception:
        logger.exception("parse_pyproject_toml: failed to parse content.")
    return deps


def _extract_pep517_deps(text: str, deps: Dict[str, str]) -> None:
    """Parse quoted package specifiers from a fragment of a TOML array."""
    for quoted in re.findall(r'"([^"]+)"', text):
        quoted = quoted.strip().split(";")[0].strip()
        m = re.match(
            r"^([A-Za-z0-9_\-\.]+)\s*(?:(==|>=|<=|~=|!=|>|<)\s*([\S]+))?",
            quoted,
        )
        if m:
            name = m.group(1).lower()
            version = m.group(3) if m.group(3) else "unknown"
            deps[name] = version


def parse_pipfile(content: str) -> Dict[str, str]:
    """
    Parse the ``[packages]`` section of a *Pipfile*.

    Handles both ``package = "version"`` and ``package = "*"`` entries.

    Returns:
        ``{package_name: version}``
    """
    deps: Dict[str, str] = {}
    try:
        in_packages = False
        for raw in content.splitlines():
            line = raw.strip()
            if re.match(r"^\[packages\]", line):
                in_packages = True
                continue
            if re.match(r"^\[", line):
                in_packages = False
                continue
            if in_packages:
                if not line or line.startswith("#"):
                    continue
                m = re.match(r'^([A-Za-z0-9_\-\.]+)\s*=\s*"([^"]*)"', line)
                if m:
                    name = m.group(1).lower()
                    version = m.group(2) if m.group(2) != "*" else "unknown"
                    deps[name] = version
    except Exception:
        logger.exception("parse_pipfile: failed to parse content.")
    return deps


def parse_package_json(content: str) -> Dict[str, str]:
    """
    Parse ``dependencies`` and ``devDependencies`` from a *package.json* file.

    Uses ``json.loads`` for reliable parsing.

    Returns:
        ``{package_name: version}``
    """
    deps: Dict[str, str] = {}
    try:
        data = json.loads(content)
        for key in ("dependencies", "devDependencies"):
            section = data.get(key, {})
            if isinstance(section, dict):
                for pkg, ver in section.items():
                    deps[pkg.lower()] = ver if isinstance(ver, str) else "unknown"
    except Exception:
        logger.exception("parse_package_json: failed to parse content.")
    return deps


def parse_package_lock(content: str) -> Dict[str, str]:
    """
    Parse package names from the top-level ``packages`` object of a
    *package-lock.json* file (npm lock file v2/v3).

    Only the package name is extracted; version is always ``"unknown"`` since
    the lock file stores resolved versions nested under each entry.

    Returns:
        ``{package_name: version_string_or_"unknown"}``
    """
    deps: Dict[str, str] = {}
    try:
        data = json.loads(content)
        packages = data.get("packages", {})
        if isinstance(packages, dict):
            for key, meta in packages.items():
                # Keys look like "node_modules/express" or ""
                if not key or not key.startswith("node_modules/"):
                    continue
                pkg_name = key.removeprefix("node_modules/").lower()
                version = (
                    meta.get("version", "unknown")
                    if isinstance(meta, dict)
                    else "unknown"
                )
                deps[pkg_name] = version
    except Exception:
        logger.exception("parse_package_lock: failed to parse content.")
    return deps


def parse_yarn_lock(content: str) -> Dict[str, str]:
    """
    Parse package names from a *yarn.lock* file.

    Yarn.lock entries look like::

        "package@^1.0.0":
          version "1.2.3"

    We extract just the package names (ignoring version specifiers in the key).

    Returns:
        ``{package_name: "unknown"}``
    """
    deps: Dict[str, str] = {}
    try:
        for line in content.splitlines():
            line = line.strip()
            # Entry headers end with ":"" and contain the package name + spec
            if line.endswith(":") and not line.startswith("#"):
                # Strip surrounding quotes and trailing colon
                entry = line.rstrip(":").strip('"').strip("'")
                # May have multiple resolutions separated by ", "
                for part in entry.split(","):
                    part = part.strip().strip('"').strip("'")
                    # The package name is before the "@version" specifier
                    # Handle scoped packages like @scope/pkg@^1.0.0
                    if part.startswith("@"):
                        m = re.match(r"^(@[^@]+)@", part)
                    else:
                        m = re.match(r"^([^@]+)@", part)
                    if m:
                        name = m.group(1).lower()
                        if name and name not in deps:
                            deps[name] = "unknown"
    except Exception:
        logger.exception("parse_yarn_lock: failed to parse content.")
    return deps


def parse_cargo_toml(content: str) -> Dict[str, str]:
    """
    Parse the ``[dependencies]`` section of a *Cargo.toml* file.

    Handles simple ``crate = "version"`` and table-style
    ``crate = { version = "..." }`` entries.

    Returns:
        ``{crate_name: version}``
    """
    deps: Dict[str, str] = {}
    try:
        in_deps = False
        for raw in content.splitlines():
            line = raw.strip()
            if re.match(r"^\[dependencies\]", line):
                in_deps = True
                continue
            if re.match(r"^\[", line):
                in_deps = False
                continue
            if in_deps:
                if not line or line.startswith("#"):
                    continue
                # Simple: name = "version"
                m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*"([^"]*)"', line)
                if m:
                    deps[m.group(1).lower()] = m.group(2)
                    continue
                # Table: name = { version = "..." }
                m2 = re.match(
                    r'^([A-Za-z0-9_\-]+)\s*=\s*\{.*?version\s*=\s*"([^"]*)"', line
                )
                if m2:
                    deps[m2.group(1).lower()] = m2.group(2)
    except Exception:
        logger.exception("parse_cargo_toml: failed to parse content.")
    return deps


def parse_go_mod(content: str) -> Dict[str, str]:
    """
    Parse ``require`` blocks from a *go.mod* file.

    Handles both single-line ``require module version`` and block form::

        require (
            module version
        )

    Returns:
        ``{module_path: version}``
    """
    deps: Dict[str, str] = {}
    try:
        in_require_block = False
        for raw in content.splitlines():
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            if line == "require (":
                in_require_block = True
                continue
            if in_require_block:
                if line == ")":
                    in_require_block = False
                    continue
                # Strip inline comment
                line = line.split("//")[0].strip()
                parts = line.split()
                if len(parts) >= 2:
                    deps[parts[0].lower()] = parts[1]
                continue
            # Single-line require
            m = re.match(r"^require\s+(\S+)\s+(\S+)", line)
            if m:
                deps[m.group(1).lower()] = m.group(2)
    except Exception:
        logger.exception("parse_go_mod: failed to parse content.")
    return deps


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

# Mapping of dependency key (lowercase) → human-readable framework name
_PYTHON_FRAMEWORKS: Dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "starlette": "Starlette",
}

_JS_FRAMEWORKS: Dict[str, str] = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "@angular/core": "Angular",
    "express": "Express",
    "svelte": "Svelte",
}

_GO_FRAMEWORKS: Dict[str, str] = {
    "github.com/gin-gonic/gin": "Gin",
    "github.com/labstack/echo": "Echo",
    "github.com/gorilla/mux": "gorilla/mux",
}


def detect_frameworks(dependencies: Dict[str, str]) -> List[str]:
    """
    Detect web frameworks from a normalised dependency dict.

    Only returns frameworks whose canonical package name is present as a key
    in *dependencies*. Never infers frameworks from filenames or indirect clues.

    Args:
        dependencies: Mapping of ``{package_name_lowercase: version}``.

    Returns:
        Sorted list of detected framework display names.
    """
    detected: List[str] = []
    lower_deps = {k.lower(): v for k, v in dependencies.items()}

    for pkg, display in _PYTHON_FRAMEWORKS.items():
        if pkg in lower_deps:
            detected.append(display)

    for pkg, display in _JS_FRAMEWORKS.items():
        if pkg in lower_deps:
            detected.append(display)

    for pkg, display in _GO_FRAMEWORKS.items():
        if pkg in lower_deps:
            detected.append(display)

    return sorted(detected)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def parse_dependency_file(filename: str, content: str) -> Dict[str, str]:
    """
    Dispatch to the appropriate parser based on *filename*.

    Args:
        filename: The bare filename (e.g. ``"requirements.txt"``).
        content:  Raw text content of the file.

    Returns:
        Normalised ``{package_name: version}`` dict.  Empty dict on failure or
        unrecognised filename.
    """
    parsers = {
        "requirements.txt": parse_requirements_txt,
        "pyproject.toml": parse_pyproject_toml,
        "Pipfile": parse_pipfile,
        "package.json": parse_package_json,
        "package-lock.json": parse_package_lock,
        "yarn.lock": parse_yarn_lock,
        "Cargo.toml": parse_cargo_toml,
        "go.mod": parse_go_mod,
    }
    parser = parsers.get(filename)
    if parser is None:
        logger.debug("parse_dependency_file: no parser for filename %r.", filename)
        return {}
    try:
        return parser(content)
    except Exception:
        logger.exception(
            "parse_dependency_file: unhandled error parsing %r.", filename
        )
        return {}
