"""
FastAPI application entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import jobs, companies, discovery, candidate, dashboard
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.models.models import Base

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create tables on startup (migrations handle schema; this is a safety net)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

    # CORS — allow Next.js frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{settings.frontend_port}",
            "http://localhost:3000",
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

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
