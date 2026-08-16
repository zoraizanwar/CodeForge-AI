"""
Database Reliability & Resilience Core Module for Step 20.
Provides connection pool configuration, transient error retries, health verification, and transaction state inspection.
"""
import time
import logging
import functools
from typing import Callable, Any, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as SATimeoutError
from app.core.database import engine, SessionLocal

logger = logging.getLogger("codeforge.database_reliability")

MAX_RETRIES = 3
INITIAL_BACKOFF = 0.5


def with_db_retry(max_retries: int = MAX_RETRIES, initial_backoff: float = INITIAL_BACKOFF):
    """
    Decorator for database operational functions. Automatically retries on transient DB failures (e.g. connection resets).
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            backoff = initial_backoff
            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except (OperationalError, SATimeoutError, DBAPIError) as e:
                    attempts += 1
                    if attempts >= max_retries:
                        logger.error(f"Database operational failure in {func.__name__} after {attempts} attempts: {e}")
                        raise
                    logger.warning(f"Transient DB failure in {func.__name__} (attempt {attempts}/{max_retries}). Retrying in {backoff:.2f}s... Error: {e}")
                    time.sleep(backoff)
                    backoff *= 2.0
                except Exception:
                    raise
        return wrapper
    return decorator


def verify_database_connectivity(timeout_seconds: float = 5.0) -> Dict[str, Any]:
    """
    Verifies database connectivity and returns detailed pool diagnostic status.
    """
    start_time = time.time()
    result = {
        "status": "healthy",
        "latency_ms": 0.0,
        "pool_size": getattr(engine.pool, "size", lambda: 0)(),
        "checkedin": getattr(engine.pool, "checkedin", lambda: 0)(),
        "checkedout": getattr(engine.pool, "checkedout", lambda: 0)(),
        "overflow": getattr(engine.pool, "overflow", lambda: 0)(),
        "error": None
    }
    
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        result["latency_ms"] = round((time.time() - start_time) * 1000.0, 2)
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        result["status"] = "unhealthy"
        result["error"] = str(e)
        
    return result


def check_transaction_health(db: Session) -> Dict[str, Any]:
    """
    Inspects current transaction state and checks for blocked queries or idle transactions (if PostgreSQL).
    """
    health_info = {
        "active_transaction": db.in_transaction(),
        "blocked_queries": 0,
        "idle_in_transaction": 0,
        "engine": engine.name
    }
    
    if engine.name == "postgresql":
        try:
            res = db.execute(text("""
                SELECT 
                    count(CASE WHEN state = 'idle in transaction' THEN 1 END) as idle_tx,
                    count(CASE WHEN wait_event_type IS NOT NULL THEN 1 END) as blocked_tx
                FROM pg_stat_activity
                WHERE pid != pg_backend_pid()
            """)).first()
            if res:
                health_info["idle_in_transaction"] = res.idle_tx or 0
                health_info["blocked_queries"] = res.blocked_tx or 0
        except Exception as e:
            logger.debug(f"Could not fetch pg_stat_activity metrics: {e}")
            
    return health_info
