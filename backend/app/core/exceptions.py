"""
Centralized Global Exception Handlers for CodeForge AI Step 13.
Ensures safe, structured API error responses with Request IDs, preserving backward compatibility.
"""
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.logging import request_id_ctx

logger = logging.getLogger("codeforge.exceptions")


class CodeForgeException(Exception):
    """Base exception for CodeForge AI application errors."""
    pass


class AIProviderException(CodeForgeException):
    """Exception raised when AI Provider call fails or returns invalid response."""
    pass


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handles HTTPException and formats structured error response."""
    req_id = request_id_ctx.get() or "unknown"
    if isinstance(exc.detail, dict):
        content = {
            "error_code": f"HTTP_{exc.status_code}",
            "request_id": req_id,
            "detail": exc.detail,
            **exc.detail
        }
    else:
        content = {
            "error_code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "detail": exc.detail,
            "request_id": req_id,
        }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles Pydantic RequestValidationError safely while preserving detail field."""
    from fastapi.encoders import jsonable_encoder
    req_id = request_id_ctx.get() or "unknown"
    safe_errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid request payload or query parameters.",
            "detail": safe_errors,
            "details": safe_errors,
            "request_id": req_id,
        }
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles unhandled global exceptions without leaking stack trace or secrets to caller."""
    req_id = request_id_ctx.get() or "unknown"
    logger.error(f"Unhandled exception on request {req_id}: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred. Please contact system support.",
            "detail": "An internal server error occurred.",
            "request_id": req_id,
        }
    )
