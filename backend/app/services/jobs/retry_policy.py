"""
Retry policy for CodeForge AI job orchestration system (Step 11).
Calculates exponential backoff delays and classifies transient vs non-transient errors.
"""
import math
import logging
from typing import Type
from app.core.config import settings

logger = logging.getLogger("codeforge.jobs.retry_policy")

# Exceptions that must NEVER be retried automatically
NON_RETRYABLE_EXCEPTIONS = (
    PermissionError,
    ValueError,
    KeyError,
    TypeError,
)

NON_RETRYABLE_KEYWORDS = [
    "permission",
    "unauthorized",
    "forbidden",
    "path traversal",
    "boundary escape",
    "invalid input",
    "jwt",
    "anti-cheating",
    "refusing to delete",
    "refusing repair",
    "safety check failed",
]


def is_transient_failure(exc: Exception) -> bool:
    """
    Determines if an exception/failure is transient and safe to retry automatically.
    Returns False for security violations, path traversals, permission errors, or validation rejections.
    """
    if isinstance(exc, NON_RETRYABLE_EXCEPTIONS):
        return False

    err_str = str(exc).lower()
    for kw in NON_RETRYABLE_KEYWORDS:
        if kw in err_str:
            return False

    return True


def calculate_exponential_backoff(
    attempt_count: int,
    base_delay: float = None,
    max_delay: float = None
) -> float:
    """
    Computes exponential backoff delay with jitter: base_delay * 2^(attempt - 1).
    Bounded by max_delay.
    """
    b_delay = base_delay if base_delay is not None else settings.JOB_RETRY_BASE_DELAY
    m_delay = max_delay if max_delay is not None else settings.JOB_RETRY_MAX_DELAY

    if attempt_count <= 0:
        return 0.0

    delay = b_delay * (2 ** (attempt_count - 1))
    return float(min(delay, m_delay))
