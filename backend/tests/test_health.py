"""
Tests for health check endpoint (/health) and startup resilience.
Verifies:
- Healthy state reports status: ok, database: up, schema_revision present.
- Database down state degrades gracefully with status: degraded, database: down, schema_revision: None.
- No sensitive database credentials or raw error messages leaked in responses.
- Application lifespan starts gracefully even when database is unreachable.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import httpx
from httpx import ASGITransport

from app.main import create_app, lifespan


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_healthy(app):
    """Test health check when database is healthy."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "up"
    assert "schema_revision" in data
    assert data["schema_revision"] is not None


@pytest.mark.asyncio
async def test_health_database_down(app):
    """Test health check when database is unreachable (graceful degradation)."""
    with patch(
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
        side_effect=Exception("Connection to postgresql://jobagent:secret@localhost:5432 failed"),
    ):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "down"
    assert data["schema_revision"] is None
    # Verify no leaked credentials or raw error text
    response_text = response.text
    assert "secret" not in response_text
    assert "password" not in response_text.lower()
    assert "postgresql://" not in response_text


@pytest.mark.asyncio
async def test_lifespan_degraded_startup(app):
    """Test that lifespan context manager does not raise when database is unreachable."""
    with patch(
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
        side_effect=Exception("Connection refused"),
    ):
        # Must not raise an exception
        async with lifespan(app):
            pass
