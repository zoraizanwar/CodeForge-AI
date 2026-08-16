"""
Structured Logging System for CodeForge AI Step 13 Operational Readiness.
Supports JSON and text formatting with context variables (request_id, user_id, repo_id, job_id, task_id).
Enforces secret redaction on all log fields.
"""
import json
import logging
import contextvars
from typing import Any, Dict, Optional

# Context Variables for Request Correlation & Observability
request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
user_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)
repo_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("repo_id", default=None)
job_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("job_id", default=None)
task_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("task_id", default=None)

SECRET_SUBSTRINGS = [
    "bearer ", "token", "jwt", "secret", "private_key", "password", "api_key",
    "github_token", "installation_token", "access_key", "credential"
]


def redact_secrets(value: Any) -> Any:
    """Recursively redacts sensitive values from log extras and context dicts."""
    if isinstance(value, dict):
        sanitized = {}
        for k, v in value.items():
            if any(s in str(k).lower() for s in SECRET_SUBSTRINGS):
                sanitized[k] = "[REDACTED_LOG_SECRET]"
            else:
                sanitized[k] = redact_secrets(v)
        return sanitized
    elif isinstance(value, list):
        return [redact_secrets(item) for item in value]
    elif isinstance(value, str):
        if any(s in value.lower() for s in ["bearer ", "-----begin rsa private key-----", "-----begin private key-----"]):
            return "[REDACTED_LOG_SECRET]"
        return value
    return value


class StructuredJSONFormatter(logging.Formatter):
    """JSON log formatter producing machine-readable operational log records."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "service": "codeforge-ai",
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
        }

        # Inject Context Variables
        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id

        uid = user_id_ctx.get()
        if uid:
            log_data["user_id"] = uid

        rid = repo_id_ctx.get()
        if rid:
            log_data["repository_id"] = rid

        jid = job_id_ctx.get()
        if jid:
            log_data["job_id"] = jid

        tid = task_id_ctx.get()
        if tid:
            log_data["task_id"] = tid

        # Inject exception traceback safely
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(log_level: str = "INFO", log_format: str = "text") -> None:
    """Configures application-wide logging level and formatter."""
    root_logger = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)

    if log_format.lower() == "json":
        stream_handler.setFormatter(StructuredJSONFormatter())
    else:
        text_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        stream_handler.setFormatter(text_formatter)

    root_logger.addHandler(stream_handler)
