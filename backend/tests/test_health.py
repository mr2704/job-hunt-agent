"""
Tests for health check endpoint (/health) and startup resilience.
Verifies:
- Healthy state reports status: ok, database: up, schema_revision present (mocked, no real DB hit).
- Missing alembic_version degrades gracefully: status: degraded, database: up, schema_revision: None.
- Database down state degrades gracefully with status: degraded, database: down, schema_revision: None.
- No sensitive database credentials or raw error messages leaked in responses.
- Application lifespan starts gracefully even when database is unreachable.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import ASGITransport

from app.main import create_app, lifespan


@pytest.fixture
def app():
    return create_app()


def _create_mock_connect_context(execute_side_effect=None, revision: str | None = "fake_rev_abc123"):
    """Helper to create a mocked async connection context manager."""
    mock_conn = AsyncMock()

    if execute_side_effect:
        mock_conn.execute.side_effect = execute_side_effect
    else:
        async def default_execute(statement, *args, **kwargs):
            mock_res = MagicMock()
            if "alembic_version" in str(statement):
                mock_res.fetchone.return_value = (revision,)
            else:
                mock_res.fetchone.return_value = (1,)
            return mock_res

        mock_conn.execute.side_effect = default_execute

    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    return mock_ctx


@pytest.mark.asyncio
async def test_health_healthy(app):
    """Test health check when database is healthy (mocked, does not hit real database)."""
    mock_ctx = _create_mock_connect_context(revision="fake_rev_abc123")
    with patch("sqlalchemy.ext.asyncio.AsyncEngine.connect", return_value=mock_ctx):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "up"
    assert data["schema_revision"] == "fake_rev_abc123"


@pytest.mark.asyncio
async def test_health_missing_alembic_version(app):
    """Test health check when database is up but alembic_version table is missing."""
    async def mock_execute(statement, *args, **kwargs):
        if "alembic_version" in str(statement):
            raise Exception("relation alembic_version does not exist")
        mock_res = MagicMock()
        mock_res.fetchone.return_value = (1,)
        return mock_res

    mock_ctx = _create_mock_connect_context(execute_side_effect=mock_execute)
    with patch("sqlalchemy.ext.asyncio.AsyncEngine.connect", return_value=mock_ctx):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "up"
    assert data["schema_revision"] is None


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
