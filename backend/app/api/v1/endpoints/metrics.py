"""
Operational Metrics API endpoint for CodeForge AI Step 14 Observability.
Provides safe, aggregated HTTP, Job, Agent, Execution, Git, AI Provider, and WebSocket statistics.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.metrics import metrics_collector
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/metrics", tags=["Observability"])
async def get_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Exposes safe aggregated operational metrics for system health monitoring.
    Requires authenticated user access. Does NOT leak secrets, source code, or private paths.
    """
    snapshot = metrics_collector.get_metrics_snapshot()
    return snapshot
