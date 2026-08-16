import datetime
from sqlalchemy import create_engine, DateTime
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings
from typing import Generator

class UTCDateTime(TypeDecorator):
    """
    Custom SQLAlchemy TypeDecorator that ensures Datetime fields are always
    returned as timezone-aware UTC datetime objects, resolving timezone inconsistencies
    between SQLite (tests) and PostgreSQL (production).
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Datetime must be timezone-aware.")
            return value.astimezone(datetime.timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.timezone.utc)
            return value.astimezone(datetime.timezone.utc)
        return value

# SQLite connection parameter handling for unit tests/local debugging
connect_args = {}
if settings.database_url_validated.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Create SQLAlchemy connection engine
engine = create_engine(
    settings.database_url_validated,
    connect_args=connect_args,
    pool_pre_ping=True  # Detect and recover from stale connections automatically
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator:
    """Dependency injection yield for database session. Ensures sessions are closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
