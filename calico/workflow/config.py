"""Configuration helpers for workflow orchestration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Container for environment-driven settings."""

    environment: str = os.getenv("ENVIRONMENT", "development")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    database_url: str | None = os.getenv("DATABASE_URL")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./data/calico.db")
    playwright_browser: str = os.getenv("PLAYWRIGHT_BROWSER", "chromium")
    playwright_headless: bool = _env_flag("PLAYWRIGHT_HEADLESS", default=True)
    playwright_stealth_mode: bool = _env_flag("PLAYWRIGHT_STEALTH_MODE", default=True)
    playwright_use_patchright: bool = _env_flag("PLAYWRIGHT_USE_PATCHRIGHT", default=True)
    neo4j_uri: str | None = os.getenv("NEO4J_URI")
    neo4j_user: str | None = os.getenv("NEO4J_USER")
    neo4j_password: str | None = os.getenv("NEO4J_PASSWORD")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    agent_max_retries: int = int(os.getenv("AGENT_MAX_RETRIES", "3"))
    agent_retry_backoff_seconds: float = float(os.getenv("AGENT_RETRY_BACKOFF", "2.0"))
    agent_error_ttl_minutes: int = int(os.getenv("AGENT_ERROR_TTL_MINUTES", "60"))
    # API server configuration
    api_server_host: str = os.getenv("API_SERVER_HOST", "0.0.0.0")
    api_server_port: int = int(os.getenv("API_SERVER_PORT", "8000"))
    
    # Backend configuration
    backend_mode: str = os.getenv("BACKEND_MODE", "mcp")
    use_mcp_backend: bool = _env_flag("USE_MCP_BACKEND", default=True)  # Legacy support
    
    # MCP backend settings
    mcp_ws_url: str = os.getenv("MCP_WS_URL", "ws://playwright-mcp:7001")
    mcp_request_timeout_seconds: float = float(os.getenv("MCP_REQUEST_TIMEOUT", "30.0"))
    mcp_session_prefix: str = os.getenv("MCP_SESSION_PREFIX", "calico")

    def resolved_database_url(self) -> str:
        """Return a SQLAlchemy-compatible database URL."""

        if self.database_url:
            return self.database_url

        sqlite_file = Path(self.sqlite_path)
        if not sqlite_file.is_absolute():
            sqlite_file = Path.cwd() / sqlite_file
        sqlite_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_file.as_posix()}"

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_user and self.neo4j_password)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
