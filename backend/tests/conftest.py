import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db

# Isolated SQLite in-memory test database URL
TEST_DATABASE_URL = "sqlite://"

@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped database engine for test runs. Initializes all model schemas."""
    engine = create_engine(
        TEST_DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    # Create all tables dynamically before tests execute
    Base.metadata.create_all(bind=engine)
    yield engine
    # Drop all tables after the test session finishes
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator:
    """Provides a transactional database session rolled back after every individual test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    connection = test_engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient equipped with mocked DB dependencies pointing to the isolated session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
from app.models.user import User

@pytest.fixture(scope="function")
def test_user(db_session):
    user = User(email="test@example.com", hashed_password="hashed_password", is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
