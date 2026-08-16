"""
Comprehensive test suite for Step 6: AI Codebase Understanding & Repository Intelligence.

Coverage:
  - Python AST parsing (classes, functions, methods, routes, imports)
  - TypeScript/JavaScript regex parsing
  - Go parsing
  - Symbol extraction
  - Route detection
  - Dependency parsing (requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml)
  - Framework detection
  - Semantic chunking (symbols, module fallback, long-function splitting)
  - Deterministic mock embeddings
  - HybridVector SQLite behavior
  - Cosine similarity fallback
  - Analysis status transitions
  - Repository ownership isolation
  - Sensitive file exclusion
  - API authentication enforcement
  - Cross-user search prevention
"""
import asyncio
import io
import json
import math
import uuid
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.knowledge import (
    CodeChunk,
    HybridVector,
    RepositoryAnalysis,
    SourceFile,
    Symbol,
)
from app.models.repository import Repository
from app.models.github import GitHubInstallation
from app.models.user import User
from app.services.code_parser import (
    detect_language,
    parse_go,
    parse_python,
    parse_typescript_javascript,
    parse_file,
)
from app.services.chunker import chunk_file, estimate_tokens, MAX_CHUNK_LINES
from app.services.dependency_parser import (
    detect_frameworks,
    parse_cargo_toml,
    parse_go_mod,
    parse_package_json,
    parse_pyproject_toml,
    parse_requirements_txt,
    parse_dependency_file,
    DEPENDENCY_FILENAMES,
)
from app.services.embeddings import MockEmbeddingProvider


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def analysis_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="analysis@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def other_analysis_user(db_session: Session) -> User:
    pw_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    u = User(email="other_analysis@codeforge.test", hashed_password=pw_hash)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def analysis_repo(db_session: Session, analysis_user: User) -> Repository:
    repo = Repository(
        user_id=analysis_user.id,
        github_repo_id=88881,
        name="analysis-repo",
        full_name="testuser/analysis-repo",
        owner="testuser",
        default_branch="main",
        status="indexed",
        local_path=f"/fake/workspaces/user_{analysis_user.id}/repo_88881",
    )
    db_session.add(repo)
    db_session.flush()
    return repo


@pytest.fixture
def other_analysis_repo(db_session: Session, other_analysis_user: User) -> Repository:
    repo = Repository(
        user_id=other_analysis_user.id,
        github_repo_id=88882,
        name="other-repo",
        full_name="other/other-repo",
        owner="other",
        default_branch="main",
        status="indexed",
        local_path=f"/fake/workspaces/user_{other_analysis_user.id}/repo_88882",
    )
    db_session.add(repo)
    db_session.flush()
    return repo


@pytest.fixture
def analysis_headers(analysis_user: User) -> dict:
    from tests.test_auth import create_test_token
    token = create_test_token(user_id=str(analysis_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_analysis_headers(other_analysis_user: User) -> dict:
    from tests.test_auth import create_test_token
    token = create_test_token(user_id=str(other_analysis_user.id))
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Language Detection
# ═══════════════════════════════════════════════════════════════════════════

def test_detect_language_python():
    assert detect_language("app/main.py") == "Python"

def test_detect_language_typescript():
    assert detect_language("src/App.tsx") == "TypeScript"

def test_detect_language_javascript():
    assert detect_language("src/index.js") == "JavaScript"

def test_detect_language_go():
    assert detect_language("main.go") == "Go"

def test_detect_language_excluded_env():
    assert detect_language(".env") is None
    assert detect_language(".env.local") is None

def test_detect_language_excluded_pem():
    assert detect_language("secrets/key.pem") is None

def test_detect_language_excluded_pyc():
    assert detect_language("app/__pycache__/main.cpython-313.pyc") is None

def test_detect_language_excluded_node_modules():
    assert detect_language("node_modules/react/index.js") is None

def test_detect_language_excluded_binary():
    assert detect_language("app.exe") is None
    assert detect_language("lib.dll") is None

def test_detect_language_ssh_key():
    assert detect_language("id_rsa") is None

def test_detect_language_markdown():
    assert detect_language("README.md") == "Markdown"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Python AST Parsing
# ═══════════════════════════════════════════════════════════════════════════

PYTHON_SAMPLE = '''
import os
from pathlib import Path

class MyService:
    def __init__(self, name: str):
        self.name = name

    def process(self, data: list) -> dict:
        return {}

def helper_function(x: int) -> int:
    return x * 2

router = None

@router.get("/users")
async def get_users():
    pass
'''

def test_python_parse_extracts_class():
    result = parse_python(PYTHON_SAMPLE, "service.py")
    assert result.error is None
    classes = [s for s in result.symbols if s.type == "class"]
    assert any(s.name == "MyService" for s in classes)

def test_python_parse_extracts_methods():
    result = parse_python(PYTHON_SAMPLE, "service.py")
    methods = [s for s in result.symbols if s.type == "method"]
    assert any("MyService.__init__" in s.name for s in methods)
    assert any("MyService.process" in s.name for s in methods)

def test_python_parse_extracts_function():
    result = parse_python(PYTHON_SAMPLE, "service.py")
    functions = [s for s in result.symbols if s.type == "function"]
    assert any(s.name == "helper_function" for s in functions)

def test_python_parse_extracts_route():
    result = parse_python(PYTHON_SAMPLE, "service.py")
    routes = [s for s in result.symbols if s.type == "route"]
    assert any(s.name == "get_users" for s in routes)

def test_python_parse_extracts_imports():
    result = parse_python(PYTHON_SAMPLE, "service.py")
    imports = [s for s in result.symbols if s.type == "import"]
    assert any("os" in s.name for s in imports)
    assert any("Path" in s.name for s in imports)

def test_python_parse_line_numbers():
    result = parse_python(PYTHON_SAMPLE, "service.py")
    cls = next(s for s in result.symbols if s.name == "MyService")
    assert cls.line_number > 0

def test_python_parse_invalid_syntax():
    result = parse_python("def broken(:\n    pass", "broken.py")
    assert result.error is not None
    assert result.symbols == []

def test_python_parse_class_bases():
    source = "class Child(Base, Mixin):\n    pass\n"
    result = parse_python(source, "child.py")
    cls = next(s for s in result.symbols if s.type == "class")
    assert "Base" in cls.metadata.get("bases", [])


# ═══════════════════════════════════════════════════════════════════════════
# 3. TypeScript / JavaScript Parsing
# ═══════════════════════════════════════════════════════════════════════════

TS_SAMPLE = '''
import React from 'react';
import { useState } from 'react';

export class UserComponent {
  render() {}
}

export function fetchUser(id: string) {
  return null;
}

const handleClick = async (event) => {
  console.log(event);
};

router.get("/api/users", (req, res) => {});
'''

def test_ts_parse_imports():
    result = parse_typescript_javascript(TS_SAMPLE, "user.tsx", "TypeScript")
    assert result.error is None
    imports = [s for s in result.symbols if s.type == "import"]
    assert any("react" in s.name for s in imports)

def test_ts_parse_class():
    result = parse_typescript_javascript(TS_SAMPLE, "user.tsx", "TypeScript")
    classes = [s for s in result.symbols if s.type == "class"]
    assert any("UserComponent" in s.name for s in classes)

def test_ts_parse_function():
    result = parse_typescript_javascript(TS_SAMPLE, "user.tsx", "TypeScript")
    fns = [s for s in result.symbols if s.type == "function"]
    assert any("fetchUser" in s.name for s in fns)

def test_ts_parse_arrow_function():
    result = parse_typescript_javascript(TS_SAMPLE, "user.tsx", "TypeScript")
    fns = [s for s in result.symbols if s.type == "function"]
    assert any("handleClick" in s.name for s in fns)

def test_ts_parse_route():
    result = parse_typescript_javascript(TS_SAMPLE, "routes.js", "JavaScript")
    routes = [s for s in result.symbols if s.type == "route"]
    assert any("/api/users" in s.name for s in routes)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Go Parsing
# ═══════════════════════════════════════════════════════════════════════════

GO_SAMPLE = '''package main

import (
    "fmt"
    "net/http"
)

type Server struct {
    port int
}

func NewServer(port int) *Server {
    return &Server{port: port}
}

func (s *Server) Start() error {
    return nil
}
'''

def test_go_parse_imports():
    result = parse_go(GO_SAMPLE, "main.go")
    assert result.error is None
    imports = [s for s in result.symbols if s.type == "import"]
    assert any("fmt" in s.name for s in imports)
    assert any("net/http" in s.name for s in imports)

def test_go_parse_struct():
    result = parse_go(GO_SAMPLE, "main.go")
    classes = [s for s in result.symbols if s.type == "class"]
    assert any("Server" in s.name for s in classes)

def test_go_parse_functions():
    result = parse_go(GO_SAMPLE, "main.go")
    fns = [s for s in result.symbols if s.type == "function"]
    assert any("NewServer" in s.name for s in fns)
    assert any("Start" in s.name for s in fns)

def test_parse_file_dispatcher():
    """parse_file() correctly dispatches to the right parser."""
    result = parse_file("app.py", "def hello(): pass\n", "Python")
    assert result.language == "Python"
    fns = [s for s in result.symbols if s.type == "function"]
    assert any(s.name == "hello" for s in fns)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Semantic Chunking
# ═══════════════════════════════════════════════════════════════════════════

def test_estimate_tokens():
    text = "hello world foo bar"
    result = estimate_tokens(text)
    assert isinstance(result, int)
    assert result > 0

def test_chunk_file_python_creates_chunks():
    source = PYTHON_SAMPLE.strip()
    parse_result = parse_python(source, "service.py")
    chunks = chunk_file("service.py", source, "Python", parse_result)
    assert len(chunks) > 0
    for c in chunks:
        assert c.content
        assert c.start_line >= 1
        assert c.end_line >= c.start_line
        assert c.token_count > 0

def test_chunk_file_each_chunk_has_language():
    source = "class A:\n    def f(self): pass\n"
    parse_result = parse_python(source, "a.py")
    chunks = chunk_file("a.py", source, "Python", parse_result)
    for c in chunks:
        assert c.language == "Python"

def test_chunk_file_long_function_splits():
    """A function > MAX_CHUNK_LINES should produce multiple chunks."""
    lines = ["def big_func():\n"] + [f"    x = {i}\n" for i in range(MAX_CHUNK_LINES + 30)]
    source = "".join(lines)
    parse_result = parse_python(source, "big.py")
    chunks = chunk_file("big.py", source, "Python", parse_result)
    assert len(chunks) >= 2

def test_chunk_file_markdown_text_chunks():
    """Text-only files should still be chunked by lines."""
    source = "\n".join([f"Line {i}" for i in range(200)])
    from app.services.code_parser import ParseResult
    parse_result = ParseResult(path="README.md", language="Markdown")
    chunks = chunk_file("README.md", source, "Markdown", parse_result)
    assert len(chunks) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# 6. Dependency Parsing
# ═══════════════════════════════════════════════════════════════════════════

def test_parse_requirements_txt_basic():
    content = "fastapi>=0.110.0\nuvicorn>=0.28.0\n# comment\nsqlalchemy\n"
    deps = parse_requirements_txt(content)
    assert "fastapi" in deps
    assert "uvicorn" in deps
    assert "sqlalchemy" in deps
    # comments must not be included
    assert all(not k.startswith("#") for k in deps)

def test_parse_pyproject_toml_project_deps():
    content = '[project]\ndependencies = [\n    "fastapi>=0.110",\n    "pydantic>=2.0",\n]\n'
    deps = parse_pyproject_toml(content)
    assert "fastapi" in deps

def test_parse_package_json():
    content = json.dumps({
        "dependencies": {"react": "^18.0.0", "axios": "^1.0.0"},
        "devDependencies": {"typescript": "^5.0.0"},
    })
    deps = parse_package_json(content)
    assert "react" in deps
    assert "typescript" in deps

def test_parse_go_mod():
    content = 'module myapp\n\ngo 1.21\n\nrequire (\n    github.com/gin-gonic/gin v1.9.1\n    golang.org/x/net v0.10.0\n)\n'
    deps = parse_go_mod(content)
    assert any("gin" in k for k in deps)

def test_parse_cargo_toml():
    content = '[package]\nname = "myapp"\n\n[dependencies]\nserde = "1.0"\ntokio = { version = "1.0", features = ["full"] }\n'
    deps = parse_cargo_toml(content)
    assert "serde" in deps

def test_dependency_filenames_set():
    assert "requirements.txt" in DEPENDENCY_FILENAMES
    assert "package.json" in DEPENDENCY_FILENAMES
    assert "go.mod" in DEPENDENCY_FILENAMES

def test_parse_dependency_file_dispatcher():
    content = "fastapi>=0.110\n"
    deps = parse_dependency_file("requirements.txt", content)
    assert "fastapi" in deps

def test_dependency_file_malformed_does_not_crash():
    # Malformed JSON for package.json
    deps = parse_package_json("NOT VALID JSON {{{{")
    assert isinstance(deps, dict)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Framework Detection
# ═══════════════════════════════════════════════════════════════════════════

def test_detect_fastapi_framework():
    deps = {"fastapi": "0.110", "uvicorn": "0.28"}
    frameworks = detect_frameworks(deps)
    assert "FastAPI" in frameworks

def test_detect_django_framework():
    deps = {"django": "4.2"}
    frameworks = detect_frameworks(deps)
    assert "Django" in frameworks

def test_detect_react_framework():
    deps = {"react": "18.0", "react-dom": "18.0"}
    frameworks = detect_frameworks(deps)
    assert "React" in frameworks

def test_detect_nextjs_framework():
    deps = {"next": "14.0"}
    frameworks = detect_frameworks(deps)
    assert "Next.js" in frameworks

def test_no_false_framework_detection():
    """Framework detection must be based on deps, not filenames."""
    deps = {}  # empty — no frameworks
    frameworks = detect_frameworks(deps)
    assert frameworks == []

def test_multiple_frameworks_detected():
    deps = {"fastapi": "0.1", "sqlalchemy": "2.0", "react": "18.0"}
    frameworks = detect_frameworks(deps)
    assert "FastAPI" in frameworks
    assert "React" in frameworks


# ═══════════════════════════════════════════════════════════════════════════
# 8. Mock Embedding Provider
# ═══════════════════════════════════════════════════════════════════════════

def test_mock_embedding_deterministic():
    provider = MockEmbeddingProvider()
    v1 = provider._text_to_vector("hello world")
    v2 = provider._text_to_vector("hello world")
    assert v1 == v2

def test_mock_embedding_different_inputs():
    provider = MockEmbeddingProvider()
    v1 = provider._text_to_vector("alpha")
    v2 = provider._text_to_vector("beta")
    assert v1 != v2

def test_mock_embedding_unit_vector():
    provider = MockEmbeddingProvider()
    v = provider._text_to_vector("test")
    magnitude = math.sqrt(sum(x * x for x in v))
    assert abs(magnitude - 1.0) < 1e-6

def test_mock_embedding_batch():
    provider = MockEmbeddingProvider()
    results = [provider._text_to_vector(t) for t in ["hello", "world", "foo"]]
    assert len(results) == 3
    assert all(len(v) == 1536 for v in results)

def test_mock_embedding_dimensions():
    provider = MockEmbeddingProvider(dimensions=384)
    v = provider._text_to_vector("test")
    assert len(v) == 384


# ═══════════════════════════════════════════════════════════════════════════
# 9. HybridVector SQLite Behavior
# ═══════════════════════════════════════════════════════════════════════════

def test_hybrid_vector_loads_json_in_sqlite(db_session: Session, analysis_repo: Repository):
    """On SQLite, embedding stores and retrieves as JSON list."""
    # Create source file
    sf = SourceFile(
        repository_id=analysis_repo.id,
        path="test_vector.py",
        language="Python",
        size_bytes=100,
        hash="deadbeef" * 8,
    )
    db_session.add(sf)
    db_session.flush()

    vec = [0.1, 0.2, 0.3] + [0.0] * 1533
    chunk = CodeChunk(
        source_file_id=sf.id,
        content="def test(): pass",
        start_line=1,
        end_line=1,
        embedding=vec,
        token_count=3,
    )
    db_session.add(chunk)
    db_session.flush()

    retrieved = db_session.query(CodeChunk).filter(CodeChunk.id == chunk.id).first()
    assert retrieved is not None
    # In SQLite it comes back as a list (JSON)
    if isinstance(retrieved.embedding, str):
        loaded = json.loads(retrieved.embedding)
    else:
        loaded = retrieved.embedding
    assert len(loaded) == 1536
    assert abs(loaded[0] - 0.1) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════
# 10. Cosine Similarity Fallback
# ═══════════════════════════════════════════════════════════════════════════

def test_cosine_similarity_identical():
    from app.api.v1.endpoints.analysis import _cosine_similarity_python
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine_similarity_python(v, v) - 1.0) < 1e-6

def test_cosine_similarity_orthogonal():
    from app.api.v1.endpoints.analysis import _cosine_similarity_python
    assert abs(_cosine_similarity_python([1, 0, 0], [0, 1, 0])) < 1e-6

def test_cosine_similarity_empty():
    from app.api.v1.endpoints.analysis import _cosine_similarity_python
    assert _cosine_similarity_python([], []) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 11. API Authentication
# ═══════════════════════════════════════════════════════════════════════════

def test_analysis_requires_auth(client: TestClient, analysis_repo: Repository):
    repo_id = str(analysis_repo.id)
    assert client.get(f"/api/v1/repositories/{repo_id}/analysis").status_code == 401
    assert client.get(f"/api/v1/repositories/{repo_id}/symbols").status_code == 401
    assert client.get(f"/api/v1/repositories/{repo_id}/dependencies").status_code == 401
    assert client.post(f"/api/v1/repositories/{repo_id}/analyze").status_code == 401
    assert client.post(f"/api/v1/repositories/{repo_id}/search", json={"query": "test"}).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 12. Repository Ownership Isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_cannot_access_other_users_analysis(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    other_analysis_headers: dict,
):
    """Other user cannot retrieve analysis for repo they don't own."""
    repo_id = str(analysis_repo.id)
    r = client.get(
        f"/api/v1/repositories/{repo_id}/analysis",
        headers=other_analysis_headers,
    )
    assert r.status_code == 404

def test_cannot_trigger_other_users_analysis(
    client: TestClient,
    analysis_repo: Repository,
    other_analysis_headers: dict,
):
    repo_id = str(analysis_repo.id)
    r = client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=other_analysis_headers,
    )
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 13. Analysis Status Transitions
# ═══════════════════════════════════════════════════════════════════════════

def test_trigger_analysis_returns_202(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    """POST /analyze should start background task and return 202."""
    repo_id = str(analysis_repo.id)
    with patch("app.api.v1.endpoints.analysis.run_analysis_pipeline", new_callable=AsyncMock) as mock_task:
        r = client.post(
            f"/api/v1/repositories/{repo_id}/analyze",
            headers=analysis_headers,
        )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] in ("pending", "queued")


def test_analysis_status_completed(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    """After analysis is set to completed, GET /analysis returns it."""
    repo_id = str(analysis_repo.id)

    # Manually insert a completed analysis record
    analysis = RepositoryAnalysis(
        repository_id=analysis_repo.id,
        status="completed",
        architecture_summary="FastAPI backend | 10 files",
        entry_points=["app/main.py"],
        dependencies_parsed={"fastapi": "0.110"},
    )
    db_session.add(analysis)
    db_session.commit()

    r = client.get(f"/api/v1/repositories/{repo_id}/analysis", headers=analysis_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert "FastAPI" in data["frameworks"]


# ═══════════════════════════════════════════════════════════════════════════
# 14. Symbols API
# ═══════════════════════════════════════════════════════════════════════════

def test_get_symbols_returns_data(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    sf = SourceFile(
        repository_id=analysis_repo.id,
        path="api.py",
        language="Python",
        size_bytes=200,
        hash="ab" * 32,
    )
    db_session.add(sf)
    db_session.flush()

    sym = Symbol(
        source_file_id=sf.id,
        name="UserService",
        type="class",
        line_number=10,
    )
    db_session.add(sym)
    db_session.commit()

    repo_id = str(analysis_repo.id)
    r = client.get(f"/api/v1/repositories/{repo_id}/symbols", headers=analysis_headers)
    assert r.status_code == 200
    symbols = r.json()
    assert any(s["name"] == "UserService" for s in symbols)


def test_get_symbols_filtered_by_type(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    sf = SourceFile(
        repository_id=analysis_repo.id,
        path="routes.py",
        language="Python",
        size_bytes=100,
        hash="cd" * 32,
    )
    db_session.add(sf)
    db_session.flush()

    db_session.add(Symbol(source_file_id=sf.id, name="get_user", type="route", line_number=5))
    db_session.add(Symbol(source_file_id=sf.id, name="HelperClass", type="class", line_number=15))
    db_session.commit()

    repo_id = str(analysis_repo.id)
    r = client.get(
        f"/api/v1/repositories/{repo_id}/symbols?symbol_type=route",
        headers=analysis_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert all(s["type"] == "route" for s in data)


# ═══════════════════════════════════════════════════════════════════════════
# 15. Dependencies API
# ═══════════════════════════════════════════════════════════════════════════

def test_get_dependencies_returns_data(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    analysis = RepositoryAnalysis(
        repository_id=analysis_repo.id,
        status="completed",
        dependencies_parsed={"react": "18.0", "next": "14.0"},
    )
    db_session.add(analysis)
    db_session.commit()

    repo_id = str(analysis_repo.id)
    r = client.get(f"/api/v1/repositories/{repo_id}/dependencies", headers=analysis_headers)
    assert r.status_code == 200
    data = r.json()
    assert "react" in data["dependencies"]
    assert "React" in data["frameworks"]
    assert "Next.js" in data["frameworks"]


# ═══════════════════════════════════════════════════════════════════════════
# 16. Semantic Search (Python fallback)
# ═══════════════════════════════════════════════════════════════════════════

def test_search_returns_results(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    sf = SourceFile(
        repository_id=analysis_repo.id,
        path="search_test.py",
        language="Python",
        size_bytes=50,
        hash="ef" * 32,
    )
    db_session.add(sf)
    db_session.flush()

    # Insert a chunk with a known embedding (call sync helper directly)
    provider = MockEmbeddingProvider()
    vec = provider._text_to_vector("authentication logic")

    chunk = CodeChunk(
        source_file_id=sf.id,
        content="def authenticate(user): return True",
        start_line=1,
        end_line=1,
        embedding=vec,
        token_count=5,
    )
    db_session.add(chunk)
    db_session.commit()

    repo_id = str(analysis_repo.id)
    r = client.post(
        f"/api/v1/repositories/{repo_id}/search",
        headers=analysis_headers,
        json={"query": "authentication logic", "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["results"][0]["file_path"] == "search_test.py"


def test_search_cross_user_isolation(
    client: TestClient,
    db_session: Session,
    analysis_repo: Repository,
    other_analysis_repo: Repository,
    other_analysis_headers: dict,
):
    """Search on one user's repo must not return other user's chunks."""
    sf = SourceFile(
        repository_id=analysis_repo.id,
        path="secret.py",
        language="Python",
        size_bytes=50,
        hash="12" * 32,
    )
    db_session.add(sf)
    db_session.flush()

    provider = MockEmbeddingProvider()
    vec = provider._text_to_vector("secret data")

    chunk = CodeChunk(
        source_file_id=sf.id,
        content="SECRET = 'hidden'",
        start_line=1,
        end_line=1,
        embedding=vec,
        token_count=2,
    )
    db_session.add(chunk)
    db_session.commit()

    # Other user searches their own (empty) repo — should NOT see this chunk
    other_repo_id = str(other_analysis_repo.id)
    r = client.post(
        f"/api/v1/repositories/{other_repo_id}/search",
        headers=other_analysis_headers,
        json={"query": "secret data", "top_k": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0


def test_search_validates_empty_query(
    client: TestClient,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    repo_id = str(analysis_repo.id)
    r = client.post(
        f"/api/v1/repositories/{repo_id}/search",
        headers=analysis_headers,
        json={"query": "   ", "top_k": 5},
    )
    assert r.status_code == 422


def test_search_validates_top_k_bounds(
    client: TestClient,
    analysis_repo: Repository,
    analysis_headers: dict,
):
    repo_id = str(analysis_repo.id)
    r = client.post(
        f"/api/v1/repositories/{repo_id}/search",
        headers=analysis_headers,
        json={"query": "test", "top_k": 999},
    )
    assert r.status_code == 422

