import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User

# Valid bcrypt dummy hash structure to execute during non-existent user lookups.
# This prevents database timing differences that disclose email existence.
DUMMY_HASH = "$2b$12$kb.J2.Wc0sN7/7542z42kOx1h2M.F57gC42zD9W3Y6uM1S4kC894."

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieves a user record matching the normalized email."""
    if not email:
        return None
    normalized_email = email.strip().lower()
    return db.query(User).filter(User.email == normalized_email).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Retrieves a user record matching the primary key UUID."""
    import uuid
    try:
        # Cast to UUID to ensure compatibility with SQLite parameters in tests
        uuid_obj = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    except ValueError:
        return None
    return db.query(User).filter(User.id == uuid_obj).first()

def register_user(db: Session, email: str, password: str) -> User:
    """
    Registers a new user inside the database.
    Normalizes email, hashes plaintext password, and persists records in PostgreSQL.
    """
    normalized_email = email.strip().lower()
    hashed = hash_password(password)
    
    new_user = User(
        email=normalized_email,
        hashed_password=hashed,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Validates user login credentials.
    Performs a constant-time hashing verification run even if the user is missing
    to prevent user enumeration side-channel timing attacks.
    """
    user = get_user_by_email(db, email)
    
    if user:
        is_valid = verify_password(password, user.hashed_password)
        if is_valid:
            return user
    else:
        # Dummy verification to balance processing time
        verify_password(password, DUMMY_HASH)
        
    return None

def create_access_token(user_id: str) -> str:
    """
    Signs a JSON Web Token containing subject claims and timezone-aware expirations.
    Uses JWT parameter settings defined in the environment configuration.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire
    }
    
    token = jwt.encode(
        payload, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return token

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT access token, returning payload dict if valid."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except Exception:
        return None
