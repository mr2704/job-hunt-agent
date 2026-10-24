"""
Core configuration — loaded from environment variables.
No secrets are hardcoded here. See .env.example for required variables.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)

# Deterministic resolution of project root and absolute .env path
_backend_dir = Path(__file__).resolve().parent.parent.parent
_repo_dir = _backend_dir.parent if _backend_dir.name == "backend" else _backend_dir
_env_file_path = _repo_dir / ".env"

KNOWN_PLACEHOLDERS = (
    "replace_with_random",
    "replace_me",
    "dev-secret-key-change-in-production",
    "dev-secret-key",
    "changeme",
    "change-in-production",
    "your_secret_key",
    "example",
)


def is_placeholder_secret(value: str) -> bool:
    """Check whether a secret string matches known template/placeholder values."""
    if not value:
        return False
    lower = value.strip().lower()
    return any(p in lower for p in KNOWN_PLACEHOLDERS)


def format_safe_validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    """
    Format Pydantic validation errors safely.
    Produces only field names and reason categories, strictly preventing
    sensitive input values from leaking into error strings or logs.
    """
    safe_errors: list[dict[str, str]] = []
    for error in exc.errors():
        field = str(error["loc"][-1]) if error.get("loc") else "unknown"
        err_type = error.get("type", "")
        msg = str(error.get("msg", "")).lower()

        if err_type == "missing":
            category = "missing"
        elif "too_short" in err_type or "min_length" in err_type or "at least" in msg:
            category = "too short"
        elif "placeholder" in msg or "placeholder" in err_type:
            category = "placeholder"
        elif "greater_than" in err_type or "less_than" in err_type:
            category = "out of range"
        else:
            category = "invalid format"

        safe_errors.append({"field": field, "category": category})
    return safe_errors


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
    # Default model sourced from official Anthropic docs (https://platform.claude.com/docs/en/models/overview):
    anthropic_model: str = "claude-sonnet-5-5"
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

    @property
    def secret_key_is_placeholder(self) -> bool:
        return is_placeholder_secret(self.secret_key)

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

    @model_validator(mode="after")
    def _validate_placeholders(self) -> Settings:
        """Reject placeholder secrets in non-development modes; warn in development."""
        if self.secret_key_is_placeholder:
            if self.app_env != "development":
                raise ValueError(
                    "Placeholder secret detected in secret_key. "
                    "Placeholders are rejected outside development mode."
                )
            logger.warning(
                "placeholder_secret_detected",
                field="secret_key",
                message="SECRET_KEY is using a known placeholder value. Set a real random key for production.",
            )

        if self.anthropic_api_key and is_placeholder_secret(self.anthropic_api_key):
            if self.app_env != "development":
                raise ValueError(
                    "Placeholder secret detected in anthropic_api_key. "
                    "Placeholders are rejected outside development mode."
                )

        if self.openai_api_key and is_placeholder_secret(self.openai_api_key):
            if self.app_env != "development":
                raise ValueError(
                    "Placeholder secret detected in openai_api_key. "
                    "Placeholders are rejected outside development mode."
                )

        return self


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
            "secret_key_is_placeholder": settings.secret_key_is_placeholder,
            "secret_key_length_valid": len(settings.secret_key) >= 32,
            "backend_port": settings.backend_port,
            "frontend_port": settings.frontend_port,
            "anthropic_model": settings.anthropic_model,
        }
    except ValidationError as exc:
        safe_errs = format_safe_validation_errors(exc)
        missing = [e["field"] for e in safe_errs if e["category"] == "missing"]
        invalid = [f"{e['field']} ({e['category']})" for e in safe_errs if e["category"] != "missing"]
        return {
            "valid": False,
            "env_file": str(_env_file_path),
            "env_file_exists": _env_file_path.is_file(),
            "missing_variables": missing,
            "invalid_variables": invalid,
            "message": (
                f"Configuration incomplete. Missing required environment variable(s): {', '.join(missing)}"
                if missing
                else f"Configuration invalid: {', '.join(invalid)}"
            ),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        safe_errs = format_safe_validation_errors(exc)
        err_summaries = [f"'{e['field']}' ({e['category']})" for e in safe_errs]
        raise RuntimeError(
            f"Configuration Error: Invalid setting(s) for {', '.join(err_summaries)}. "
            f"Please check your environment configuration or .env file."
        ) from None
