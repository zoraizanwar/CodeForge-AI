import bcrypt

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt.
    Encodes the string to bytes, generates a secure salt, and returns a decoded string hash.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a bcrypt hash in constant-time.
    Safely captures decoding and format exceptions to prevent timing attacks.
    """
    if not password or not hashed_password:
        return False
    try:
        password_bytes = password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False
