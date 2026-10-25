"""
Safe read-only settings API.
Exposes only non-sensitive configuration parameters — never secrets, passwords, or keys.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SafeSettingsOut(BaseModel):
    app_env: str
    llm_provider: str
    llm_model: str
    crawl_rate_limit_rps: float
    max_upload_size_mb: int


@router.get("", response_model=SafeSettingsOut)
async def get_safe_settings() -> SafeSettingsOut:
    """Return read-only, non-sensitive application settings."""
    cfg = get_settings()
    return SafeSettingsOut(
        app_env=cfg.app_env,
        llm_provider=cfg.llm_provider,
        llm_model=cfg.llm_model,
        crawl_rate_limit_rps=cfg.crawl_rate_limit_rps,
        max_upload_size_mb=cfg.max_upload_size_mb,
    )
