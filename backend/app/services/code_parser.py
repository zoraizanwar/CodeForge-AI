"""
AST-based code parser for repository intelligence (Step 6).

Supports:
  - Python   : native `ast` module
  - TypeScript / JavaScript : regex-based symbol extraction
  - Go       : regex-based symbol extraction

Design: never raises for a single file failure — errors are caught per-file
and returned as a ParseResult with an error message.
"""
import ast
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger("codeforge.parser")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParsedSymbol:
    name: str
    type: str           # class | function | method | route | import
    line_number: int
    end_line_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    path: str
    language: str
    symbols: List[ParsedSymbol] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    ".py":   "Python",
    ".ts":   "TypeScript",
    ".tsx":  "TypeScript",
    ".js":   "JavaScript",
    ".jsx":  "JavaScript",
    ".go":   "Go",
    ".rs":   "Rust",
    ".java": "Java",
    ".cs":   "C#",
    ".cpp":  "C++",
    ".c":    "C",
    ".rb":   "Ruby",
    ".php":  "PHP",
    ".swift": "Swift",
    ".kt":   "Kotlin",
    ".md":   "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml":  "YAML",
    ".toml": "TOML",
    ".html": "HTML",
    ".css":  "CSS",
    ".scss": "SCSS",
    ".sql":  "SQL",
    ".sh":   "Shell",
    ".bash": "Shell",
    ".ps1":  "PowerShell",
    ".dockerfile": "Dockerfile",
}

# Extensions that should be indexed for content but not AST-parsed
TEXT_ONLY_LANGUAGES = {"Markdown", "JSON", "YAML", "TOML", "HTML", "CSS", "SCSS", "SQL", "Shell", "PowerShell", "Dockerfile"}

# Files excluded from indexing (credentials / binaries / etc.)
EXCLUDED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.staging",
    "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa",
    ".htpasswd",
}
EXCLUDED_EXTENSIONS = {
    ".pem", ".key", ".crt", ".cert", ".pfx", ".p12", ".der",
    ".pyc", ".pyo", ".class", ".o", ".obj", ".a", ".lib",
    ".so", ".dll", ".exe", ".bin", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".lock",  # yarn.lock, package-lock etc. are parsed separately via deps
}
EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", ".cache", "coverage",
    "target", "vendor",
}


def detect_language(path: str) -> Optional[str]:
    """Return the language label for a file path, or None if excluded."""
    p = Path(path)
    name = p.name.lower()
    ext = p.suffix.lower()

    if name in EXCLUDED_FILENAMES:
        return None
    if ext in EXCLUDED_EXTENSIONS:
        return None
    if any(part in EXCLUDED_DIRS for part in p.parts):
        return None

    # Special cases
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "Dockerfile"
    if name in ("makefile", "gnumakefile"):
        return "Makefile"

    return EXTENSION_TO_LANGUAGE.get(ext)


def should_parse_ast(language: str) -> bool:
    """Return True if we can attempt AST/symbol extraction for this language."""
    return language not in TEXT_ONLY_LANGUAGES


# ---------------------------------------------------------------------------
# Python parser
# ---------------------------------------------------------------------------

class _RouteCollector(ast.NodeVisitor):
    """Collect FastAPI/Flask/Django route decorators from Python AST."""

    ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "route", "api_view"}

    def __init__(self):
        self.routes: list[tuple[str, int, int]] = []  # (name, start, end)

    def _is_route_decorator(self, decorator) -> bool:
        # @router.get("/path")  or  @app.get("/path")
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute):
                return func.attr.lower() in self.ROUTE_DECORATORS
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        for dec in node.decorator_list:
            if self._is_route_decorator(dec):
                self.routes.append((node.name, node.lineno, getattr(node, "end_lineno", None)))
                break
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def parse_python(source: str, path: str) -> ParseResult:
    """Parse Python source using the stdlib `ast` module."""
    result = ParseResult(path=path, language="Python")
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        result.error = f"SyntaxError at line {exc.lineno}: {exc.msg}"
        return result

    # Collect imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.symbols.append(ParsedSymbol(
                    name=alias.name,
                    type="import",
                    line_number=node.lineno,
                    metadata={"alias": alias.asname},
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result.symbols.append(ParsedSymbol(
                    name=f"{module}.{alias.name}" if module else alias.name,
                    type="import",
                    line_number=node.lineno,
                    metadata={"from": module, "alias": alias.asname},
                ))

    # Collect routes first (so we can tag functions that are routes)
    route_collector = _RouteCollector()
    route_collector.visit(tree)
    route_names = {(name, lineno) for name, lineno, _ in route_collector.routes}

    # Walk top-level and class members
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            args_info = {}
            result.symbols.append(ParsedSymbol(
                name=node.name,
                type="class",
                line_number=node.lineno,
                end_line_number=getattr(node, "end_lineno", None),
                metadata={"bases": [ast.unparse(b) for b in node.bases] if node.bases else []},
            ))
            # Methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in item.args.args]
                    decorators = []
                    for d in item.decorator_list:
                        try:
                            decorators.append(ast.unparse(d))
                        except Exception:
                            pass
                    result.symbols.append(ParsedSymbol(
                        name=f"{node.name}.{item.name}",
                        type="method",
                        line_number=item.lineno,
                        end_line_number=getattr(item, "end_lineno", None),
                        metadata={"args": args, "decorators": decorators},
                    ))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Only top-level functions (not inside classes — handled above)
            is_route = (node.name, node.lineno) in route_names
            args = [a.arg for a in node.args.args]
            decorators = []
            for d in node.decorator_list:
                try:
                    decorators.append(ast.unparse(d))
                except Exception:
                    pass
            result.symbols.append(ParsedSymbol(
                name=node.name,
                type="route" if is_route else "function",
                line_number=node.lineno,
                end_line_number=getattr(node, "end_lineno", None),
                metadata={"args": args, "decorators": decorators},
            ))

    return result


# ---------------------------------------------------------------------------
# TypeScript / JavaScript parser (regex-based)
# ---------------------------------------------------------------------------

_TS_CLASS_RE = re.compile(
    r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE
)
_TS_FUNCTION_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE
)
_TS_ARROW_RE = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(", re.MULTILINE
)
_TS_IMPORT_RE = re.compile(
    r"^import\s+(?:.*?from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE
)
_TS_ROUTE_RE = re.compile(
    r"(?:router|app)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]*)['\"]",
    re.MULTILINE | re.IGNORECASE,
)


def _line_number_for_match(source: str, match) -> int:
    return source[:match.start()].count("\n") + 1


def parse_typescript_javascript(source: str, path: str, language: str) -> ParseResult:
    result = ParseResult(path=path, language=language)
    try:
        for m in _TS_IMPORT_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(1), type="import",
                line_number=_line_number_for_match(source, m),
            ))
        for m in _TS_CLASS_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(1), type="class",
                line_number=_line_number_for_match(source, m),
            ))
        for m in _TS_FUNCTION_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(1), type="function",
                line_number=_line_number_for_match(source, m),
            ))
        for m in _TS_ARROW_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(1), type="function",
                line_number=_line_number_for_match(source, m),
                metadata={"arrow": True},
            ))
        for m in _TS_ROUTE_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(2) or "(root)",
                type="route",
                line_number=_line_number_for_match(source, m),
                metadata={"method": m.group(1).upper()},
            ))
    except Exception as exc:
        result.error = str(exc)
    return result


# ---------------------------------------------------------------------------
# Go parser (regex-based)
# ---------------------------------------------------------------------------

_GO_FUNC_RE = re.compile(r"^func\s+(?:\(\w+\s+[\w\*]+\)\s+)?(\w+)\s*\(", re.MULTILINE)
_GO_TYPE_RE = re.compile(r"^type\s+(\w+)\s+struct", re.MULTILINE)
_GO_IMPORT_RE = re.compile(r'"([^"]+)"', re.MULTILINE)


def parse_go(source: str, path: str) -> ParseResult:
    result = ParseResult(path=path, language="Go")
    try:
        # Import block
        in_import = False
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("import ("):
                in_import = True
                continue
            if in_import:
                if stripped == ")":
                    in_import = False
                    continue
                m = re.search(r'"([^"]+)"', stripped)
                if m:
                    result.symbols.append(ParsedSymbol(
                        name=m.group(1), type="import", line_number=i
                    ))
            elif stripped.startswith('import "'):
                m = re.search(r'"([^"]+)"', stripped)
                if m:
                    result.symbols.append(ParsedSymbol(
                        name=m.group(1), type="import", line_number=i
                    ))

        for m in _GO_FUNC_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(1), type="function",
                line_number=_line_number_for_match(source, m),
            ))
        for m in _GO_TYPE_RE.finditer(source):
            result.symbols.append(ParsedSymbol(
                name=m.group(1), type="class",
                line_number=_line_number_for_match(source, m),
            ))
    except Exception as exc:
        result.error = str(exc)
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def parse_file(path: str, source: str, language: str) -> ParseResult:
    """
    Dispatch to the appropriate parser for the given language.
    Never raises — errors are embedded in ParseResult.error.
    """
    if not should_parse_ast(language):
        return ParseResult(path=path, language=language)  # text-only

    try:
        if language == "Python":
            return parse_python(source, path)
        elif language in ("TypeScript", "JavaScript"):
            return parse_typescript_javascript(source, path, language)
        elif language == "Go":
            return parse_go(source, path)
        else:
            # Language recognised but no dedicated parser yet
            return ParseResult(path=path, language=language)
    except Exception as exc:
        logger.warning("Unexpected parser error for %s: %s", path, exc)
        return ParseResult(path=path, language=language, error=str(exc))
