"""
Discovery API router — trigger and monitor job discovery runs.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.schemas import DiscoveryRunRequest, DiscoveryRunResponse
from app.services.discovery.discovery_service import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])

_last_stats: dict = {}


@router.post("/run", response_model=DiscoveryRunResponse)
async def trigger_discovery(
    request: DiscoveryRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DiscoveryRunResponse:
    """
    Trigger a job discovery run. Runs in the background.
    max_companies=None means crawl all companies.
    """
    service = DiscoveryService(db)
    # Run inline for now (Phase 1); move to Celery in Phase 7
    stats = await service.run_discovery(
        max_companies=request.max_companies,
        fetch_jd=request.fetch_jd,
    )
    global _last_stats
    _last_stats = stats
    return DiscoveryRunResponse(status="complete", stats=stats)


@router.get("/status")
async def discovery_status() -> dict:
    """Return the stats from the most recent discovery run."""
    return _last_stats or {"status": "no_run_yet"}
