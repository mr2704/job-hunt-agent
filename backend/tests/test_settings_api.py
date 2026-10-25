"""
Tests for safe read-only settings API (/api/v1/settings).
Asserts:
- Endpoint returns safe, non-sensitive configuration parameters.
- No secret-like values, API keys, database credentials, or passwords ever appear in response.
"""
from __future__ import annotations

import httpx
from httpx import ASGITransport
import pytest

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_get_safe_settings_success(app):
    """Verify safe settings endpoint returns 200 with expected non-sensitive keys."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/settings")

    assert resp.status_code == 200
    data = resp.json()
    assert "app_env" in data
    assert "llm_provider" in data
    assert "llm_model" in data
    assert "crawl_rate_limit_rps" in data
    assert "max_upload_size_mb" in data


@pytest.mark.asyncio
async def test_safe_settings_no_secrets_leaked(app):
    """Verify that no sensitive config values, secrets, or passwords appear in settings response."""
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/settings")

    assert resp.status_code == 200
    data = resp.json()
    text_content = resp.text.lower()

    # Disallowed sensitive keys must not be present
    sensitive_keys = {
        "secret_key",
        "database_url",
        "database_url_sync",
        "anthropic_api_key",
        "openai_api_key",
        "celery_broker_url",
        "celery_result_backend",
        "password",
    }
    for key in sensitive_keys:
        assert key not in data, f"Sensitive key '{key}' leaked in settings output!"

    # Actual secret values must not appear anywhere in the response text
    secret_values = [
        settings.secret_key,
        settings.database_url,
        settings.database_url_sync,
        settings.celery_broker_url,
        settings.celery_result_backend,
    ]
    if settings.anthropic_api_key:
        secret_values.append(settings.anthropic_api_key)
    if settings.openai_api_key:
        secret_values.append(settings.openai_api_key)

    for val in secret_values:
        if val and len(str(val)) > 4:
            assert str(val).lower() not in text_content, "Sensitive secret value found in settings response text!"
