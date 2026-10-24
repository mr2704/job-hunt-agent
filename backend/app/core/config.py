"""
Core configuration — loaded from environment variables.
No secrets are hardcoded here. See .env.example for required variables.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Deterministic resolution of project root and absolute .env path
_backend_dir = Path(__file__).resolve().parent.parent.parent
_repo_dir = _backend_dir.parent if _backend_dir.name == "backend" else _backend_dir
_env_file_path = _repo_dir / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Deterministic single absolute path to project root .env
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    secret_key: str = Field(..., min_length=32)
    backend_port: int = 8000
    frontend_port: int = 3000
    base_dir: Path = _repo_dir

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(..., description="Async SQLAlchemy URL (asyncpg)")
    database_url_sync: str = Field(..., description="Sync SQLAlchemy URL (psycopg2)")

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    openai_model: str = "gpt-4o"

    @property
    def llm_api_key(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key

    @property
    def llm_model(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        return self.openai_model

    # ── Discovery ─────────────────────────────────────────────────────────────
    bsm_base_url: str = "https://www.bangalorestartupmap.com"
    crawl_rate_limit_rps: float = 1.0
    crawl_max_retries: int = 3
    crawl_timeout_seconds: int = 30

    # ── File storage ──────────────────────────────────────────────────────────
    upload_dir: Path = Path("./candidate_data")
    max_upload_size_mb: int = 50

    @property
    def upload_dir_abs(self) -> Path:
        p = self.upload_dir
        if not p.is_absolute():
            p = self.base_dir / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── LaTeX ─────────────────────────────────────────────────────────────────
    latex_compiler: str = "pdflatex"
    latex_max_compile_attempts: int = 3

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator("upload_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v: str | Path) -> Path:
        return Path(v)


def validate_config() -> dict[str, Any]:
    """
    Safely validate the application configuration.
    Identifies missing required variables and validation errors without
    exposing sensitive secret values, credentials, or connection strings.
    """
    try:
        settings = Settings()  # type: ignore[call-arg]
        return {
            "valid": True,
            "env_file": str(_env_file_path),
            "env_file_exists": _env_file_path.is_file(),
            "missing_variables": [],
            "configured_required_variables": [
                "secret_key",
                "database_url",
                "database_url_sync",
            ],
            "app_env": settings.app_env,
            "backend_port": settings.backend_port,
            "frontend_port": settings.frontend_port,
        }
    except ValidationError as exc:
        missing: list[str] = []
        invalid: list[str] = []
        for error in exc.errors():
            loc = str(error["loc"][0])
            if error.get("type") == "missing":
                missing.append(loc)
            else:
                invalid.append(loc)
        return {
            "valid": False,
            "env_file": str(_env_file_path),
            "env_file_exists": _env_file_path.is_file(),
            "missing_variables": missing,
            "invalid_variables": invalid,
            "message": (
                f"Configuration incomplete. Missing required environment variable(s): {', '.join(missing)}"
                if missing
                else "Configuration has invalid settings."
            ),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(err["loc"][0]) for err in exc.errors() if err.get("type") == "missing"]
        if missing:
            raise RuntimeError(
                f"Configuration Error: Missing required environment variable(s): {', '.join(missing)}. "
                f"Please ensure '{_env_file_path}' exists (see .env.example) or environment variables are set."
            ) from None
        raise
