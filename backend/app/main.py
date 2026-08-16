import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware, ProductionSecurityHeadersMiddleware
from app.core.exceptions import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.core.database import get_db
from app.api.v1.router import router as api_v1_router
from app.services.jobs import run_worker_loop, stop_worker_loop

# Initialize structured logging system
configure_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)
logger = logging.getLogger("codeforge.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown lifecycle tasks for the application."""
    logger.info("Initializing CodeForge AI backend processes & durable job worker...")
    worker_task = asyncio.create_task(run_worker_loop())
    yield
    logger.info("Shutting down CodeForge AI backend processes & durable job worker...")
    stop_worker_loop()
    try:
        await asyncio.wait_for(worker_task, timeout=5.0)
    except Exception:
        pass


app = FastAPI(
    title="CodeForge AI",
    description="Backend services for CodeForge AI: Your AI Software Engineer.",
    version="0.1.0",
    lifespan=lifespan
)

# Custom correlation and security headers middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(ProductionSecurityHeadersMiddleware)

# CORS middleware configuration using parsed settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Register centralized exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

from app.api.v1.endpoints.metrics import router as metrics_router

# Versioned router mounting
app.include_router(api_v1_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="")


@app.get("/health", tags=["Diagnostics"])
async def health_check():
    """Liveness probe. Verifies application server is listening."""
    return {
        "status": "ok",
        "service": "codeforge-ai",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/ready", tags=["Diagnostics"])
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe. Verifies Database, pgvector, workspace, and job queue system readiness."""
    readiness = {
        "status": "ready",
        "services": {
            "database": "ok",
            "pgvector": "ok",
            "workspace": "ok",
            "job_queue": "ok"
        }
    }

    # 1. Test database connectivity
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Readiness check failed - Database unreachable: {str(e)}")
        readiness["services"]["database"] = "error"
        readiness["status"] = "not_ready"

    # 2. Check pgvector extension
    try:
        res = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).fetchone()
        if not res and not settings.ENV == "testing":
            readiness["services"]["pgvector"] = "not_installed"
    except Exception as e:
        readiness["services"]["pgvector"] = "unavailable"

    # 3. Check workspace directory
    try:
        os.makedirs(settings.workspace_root_resolved, exist_ok=True)
    except Exception as e:
        logger.error(f"Readiness check failed - Workspace root un-writable: {str(e)}")
        readiness["services"]["workspace"] = "error"
        readiness["status"] = "not_ready"

    # 4. Check job queue table accessibility
    try:
        db.execute(text("SELECT count(id) FROM agent_jobs"))
    except Exception as e:
        logger.error(f"Readiness check failed - Job queue inaccessible: {str(e)}")
        readiness["services"]["job_queue"] = "error"
        readiness["status"] = "not_ready"

    if readiness["status"] != "ready":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=readiness
        )

    return readiness


@app.get("/health/database", tags=["Diagnostics"])
async def health_database():
    """Returns database connection pool diagnostics."""
    from app.core.database_reliability import verify_database_connectivity
    return verify_database_connectivity()


@app.get("/health/workers", tags=["Diagnostics"])
async def health_workers(db: Session = Depends(get_db)):
    """Returns active background worker lease health."""
    now = datetime.datetime.now(datetime.timezone.utc)
    from app.models.job import AgentJob
    active_jobs = db.query(AgentJob).filter(AgentJob.status == "running", AgentJob.lease_expires_at > now).all()
    stale_jobs = db.query(AgentJob).filter(AgentJob.status.in_(["running", "cancelling"]), AgentJob.lease_expires_at < now).count()
    return {
        "status": "healthy" if stale_jobs == 0 else "degraded",
        "active_worker_leases": len({j.worker_id for j in active_jobs if j.worker_id}),
        "running_jobs": len(active_jobs),
        "stale_jobs_count": stale_jobs
    }


@app.get("/health/recovery", tags=["Diagnostics"])
async def health_recovery(db: Session = Depends(get_db)):
    """Returns disaster recovery readiness score."""
    from app.services.recovery.disaster_recovery_service import DisasterRecoveryService
    return DisasterRecoveryService.get_recovery_readiness_report(db)


@app.get("/health/detailed", tags=["Diagnostics"])
async def health_detailed(db: Session = Depends(get_db)):
    """Returns aggregated system health overview."""
    from app.services.recovery.disaster_recovery_service import DisasterRecoveryService
    return DisasterRecoveryService.get_recovery_readiness_report(db)

