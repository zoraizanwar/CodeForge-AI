"""
Standardized Operational Error Classifier for CodeForge AI Step 14 Observability.
Categorizes system, API, database, security, and agent errors into standardized domain categories.
"""
from typing import Union, Dict, Any
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import CodeForgeException, AIProviderException


ERROR_CATEGORIES = {
    "authentication": "Authentication failure, invalid or expired JWT token.",
    "authorization": "Permission denied, tenant isolation violation, or unauthorized resource access.",
    "validation": "Invalid request payload, invalid parameters, or schema validation failure.",
    "repository": "Repository workspace error, file system access, or workspace root missing.",
    "indexing": "AST parsing failure, language detection issue, or code chunking error.",
    "ai_provider": "LLM model error, Grok API timeout, or provider quota exceeded.",
    "execution": "Sandboxed container failure, execution timeout, or test runner error.",
    "job": "Background job failure, claim contention, or max retries exceeded.",
    "github": "GitHub App OAuth handshake failure or GitHub API token rejection.",
    "git": "Git branch creation error, patch application failure, commit error, or push rejection.",
    "database": "PostgreSQL connection error, query timeout, or database constraint violation.",
    "security": "Path traversal attempt, secret leak, zip bomb, or anti-cheating rule trigger.",
    "infrastructure": "System startup failure, missing environment configuration, or memory limit.",
    "unknown": "Unclassified internal server error.",
}


def classify_error(exc: Union[Exception, str, Dict[str, Any]]) -> str:
    """
    Maps an exception or error string into one of the 14 standardized error categories.
    """
    if exc is None:
        return "unknown"

    if isinstance(exc, AIProviderException):
        return "ai_provider"
    elif isinstance(exc, RequestValidationError):
        return "validation"
    elif isinstance(exc, HTTPException):
        if exc.status_code in [401]:
            return "authentication"
        elif exc.status_code in [403]:
            return "authorization"
        elif exc.status_code in [400, 422]:
            return "validation"
        elif exc.status_code in [404]:
            return "repository"
        elif exc.status_code in [503, 504]:
            return "infrastructure"

    err_str = str(exc).lower()

    if any(k in err_str for k in ["jwt", "token expired", "unauthenticated", "invalid credentials", "login failed"]):
        return "authentication"
    elif any(k in err_str for k in ["unauthorized", "permission denied", "forbidden", "tenant", "access denied"]):
        return "authorization"
    elif any(k in err_str for k in ["validation", "invalid input", "value_error", "required field"]):
        return "validation"
    elif any(k in err_str for k in ["traversal", "zip bomb", "sensitive file", "secret leak", "anti-cheating", "sanitization"]):
        return "security"
    elif any(k in err_str for k in ["git", "branch", "commit", "push", "pull request", "patch"]):
        return "git"
    elif any(k in err_str for k in ["github", "installation", "oauth"]):
        return "github"
    elif any(k in err_str for k in ["grok", "llm", "ai provider", "openai", "embedding"]):
        return "ai_provider"
    elif any(k in err_str for k in ["sandbox", "execution", "test runner", "pytest", "subprocess"]):
        return "execution"
    elif any(k in err_str for k in ["job", "worker", "queue", "retry"]):
        return "job"
    elif any(k in err_str for k in ["indexing", "chunker", "ast parse", "symbol"]):
        return "indexing"
    elif any(k in err_str for k in ["repository", "workspace", "zipball"]):
        return "repository"
    elif any(k in err_str for k in ["postgres", "sqlalchemy", "database", "psycopg", "sql"]):
        return "database"
    elif any(k in err_str for k in ["connection refused", "timeout", "network", "server error"]):
        return "infrastructure"

    return "unknown"
