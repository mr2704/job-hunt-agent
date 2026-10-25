"""
FastAPI application entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import candidate, companies, dashboard, discovery, jobs, settings
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging

settings_cfg = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup probe: test connectivity with SELECT 1, degrade gracefully (Alembic owns schema)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        # Gracefully degrade startup if database is unreachable; do not crash
        pass
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Job Discovery Agent",
        description=(
            "Discovers entry-level startup jobs in Bangalore, evaluates eligibility, "
            "tailors resumes, and tracks applications. "
            "Candidate profile starts empty — upload your resume to begin."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow Next.js frontend (localhost and 127.0.0.1)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{settings_cfg.frontend_port}",
            "http://localhost:3000",
            f"http://127.0.0.1:{settings_cfg.frontend_port}",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    prefix = "/api/v1"
    app.include_router(dashboard.router, prefix=prefix)
    app.include_router(jobs.router, prefix=prefix)
    app.include_router(companies.router, prefix=prefix)
    app.include_router(discovery.router, prefix=prefix)
    app.include_router(candidate.router, prefix=prefix)
    app.include_router(settings.router, prefix=prefix)

    @app.get("/health")
    async def health() -> dict:
        db_status = "down"
        schema_rev: str | None = None
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                db_status = "up"
                try:
                    result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                    row = result.fetchone()
                    if row and row[0]:
                        schema_rev = str(row[0])
                except Exception:
                    schema_rev = None
        except Exception:
            db_status = "down"

        is_healthy = db_status == "up" and schema_rev is not None
        return {
            "status": "ok" if is_healthy else "degraded",
            "database": db_status,
            "schema_revision": schema_rev,
            "version": "0.1.0",
        }

    return app


app = create_app()

