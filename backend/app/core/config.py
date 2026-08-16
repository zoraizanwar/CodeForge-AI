from typing import List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Search for .env in current dir or parent dir to support running from root or backend
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/codeforge"
    SECRET_KEY: str = "dev_secret_key_1234567890_codeforge_foundation"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    FRONTEND_URL: str = "http://localhost:5174"
    GROK_API_KEY: str = "mock-grok-api-key-for-local-testing"

    GROK_MODEL: str = "grok-2-1212"
    ENV: str = "development"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or console
    GUNICORN_WORKERS: int = 4

    # Step 14 Observability & Performance Monitoring Thresholds
    SLOW_REQUEST_THRESHOLD_MS: float = 2000.0
    SLOW_JOB_THRESHOLD_MS: float = 30000.0
    SLOW_ANALYSIS_THRESHOLD_MS: float = 10000.0
    AUDIT_RETENTION_DAYS: int = 30

    # JWT Authentication Config (No default value allowed for secret key in production)
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # GitHub App Configuration (No default values in production)
    GITHUB_APP_ID: Optional[int] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_PRIVATE_KEY_PATH: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    GITHUB_APP_NAME: str = "codeforge-ai-software-engineer"

    # Workspace directory settings
    WORKSPACE_ROOT: str = "workspaces"

    # Embedding provider: "mock" (default, offline) | "grok" (if API supports embeddings)
    EMBEDDING_PROVIDER: str = "mock"

    # Step 11 Durable Job Orchestration Settings
    JOB_WORKER_CONCURRENCY: int = 5
    JOB_MAX_CONCURRENT_PER_USER: int = 3
    JOB_MAX_CONCURRENT_PER_REPOSITORY: int = 2
    JOB_MAX_ATTEMPTS: int = 3
    JOB_RETRY_BASE_DELAY: int = 2
    JOB_RETRY_MAX_DELAY: int = 30
    JOB_POLL_INTERVAL: float = 1.0
    JOB_STALE_TIMEOUT: int = 600
    JOB_WS_HEARTBEAT_INTERVAL: int = 15

    # Step 12 Multi-Agent Confidence Escalation Thresholds
    AGENT_MIN_CONFIDENCE: float = 0.70
    AGENT_REVIEW_THRESHOLD: float = 0.80
    AGENT_SECURITY_THRESHOLD: float = 0.85
    AGENT_REPAIR_THRESHOLD: float = 0.75

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> 'Settings':
        import os
        import sys
        # Check if executing in a test suite runner
        is_testing = (
            ("pytest" in sys.modules and not os.environ.get("FORCE_PROD_CONFIG_CHECK")) or 
            "PYTEST_CURRENT_TEST" in os.environ or 
            self.ENV == "testing" or
            any("alembic" in arg for arg in sys.argv)
        )
        if not is_testing and not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be configured in non-testing environments.")
        if (self.ENV == "production" or self.ENVIRONMENT == "production") and not os.environ.get("FORCE_PROD_CONFIG_CHECK_DISABLE"):
            if self.JWT_SECRET_KEY in ["test_jwt_secret_key_mock_123456789_codeforge_auth", "dev_secret_key_1234567890_codeforge_foundation"]:
                raise ValueError("Production mode requires a strong, non-default JWT_SECRET_KEY.")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Wildcard CORS_ORIGINS '*' is forbidden in production environments.")
        if is_testing and not self.JWT_SECRET_KEY:
            self.JWT_SECRET_KEY = "test_jwt_secret_key_mock_123456789_codeforge_auth"
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        """Parses the comma-separated CORS_ORIGINS string into a list of strings."""
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]

    @property
    def database_url_validated(self) -> str:
        """Safely URL-encodes special characters in the database password if present."""
        url = self.DATABASE_URL
        if not url or "://" not in url:
            return url
        try:
            scheme, rest = url.split("://", 1)
            if "/" in rest:
                user_host, path = rest.split("/", 1)
            else:
                user_host, path = rest, ""
            
            if "@" in user_host:
                userinfo, host = user_host.rsplit("@", 1)
                if ":" in userinfo:
                    username, password = userinfo.split(":", 1)
                    from urllib.parse import quote_plus
                    encoded_password = quote_plus(password)
                    reconstructed = f"{scheme}://{username}:{encoded_password}@{host}"
                    if path:
                        reconstructed += f"/{path}"
                    return reconstructed
            return url
        except Exception:
            return url

    @property
    def github_private_key_resolved_path(self) -> str:
        """Resolves the GITHUB_PRIVATE_KEY_PATH relative to the project root directory."""
        if not self.GITHUB_PRIVATE_KEY_PATH:
            return ""
        
        path = self.GITHUB_PRIVATE_KEY_PATH
        import os
        if not os.path.isabs(path):
            # Resolve relative to the project root folder (three levels up from backend/app/core/config.py)
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            
            # If GITHUB_PRIVATE_KEY_PATH is just the filename, check secrets/ folder first
            if os.path.basename(path) == path:
                secrets_path = os.path.join(project_root, "secrets", path)
                if os.path.exists(secrets_path):
                    return secrets_path
                    
            return os.path.abspath(os.path.join(project_root, path))
        return path

    @property
    def workspace_root_resolved(self) -> str:
        """Resolves the WORKSPACE_ROOT path relative to the project root directory."""
        import os
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        return os.path.abspath(os.path.join(project_root, self.WORKSPACE_ROOT))

settings = Settings()


