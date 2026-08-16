"""
Production Security Headers and Correlation Middleware for CodeForge AI Step 13.
Injects unique request correlation IDs (X-Request-ID) and enforces production HTTP security headers.
"""
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import request_id_ctx, user_id_ctx, repo_id_ctx

logger = logging.getLogger("codeforge.middleware")


import time
from app.core.metrics import metrics_collector
from app.core.config import settings

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Injects or propagates X-Request-ID into request context, records metrics, and monitors latency."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        user_token = user_id_ctx.set(None)
        repo_token = repo_id_ctx.set(None)

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            response.headers["X-Request-ID"] = req_id
            metrics_collector.record_http_request(response.status_code, duration_ms)

            if duration_ms > settings.SLOW_REQUEST_THRESHOLD_MS:
                logger.warning(
                    f"Slow Request Detected: {request.method} {request.url.path} "
                    f"took {duration_ms:.2f}ms (Threshold: {settings.SLOW_REQUEST_THRESHOLD_MS}ms) "
                    f"Status: {response.status_code} RequestID: {req_id}"
                )
            return response
        finally:
            request_id_ctx.reset(token)
            user_id_ctx.reset(user_token)
            repo_id_ctx.reset(repo_token)


class ProductionSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces production HTTP security headers on all API responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response
