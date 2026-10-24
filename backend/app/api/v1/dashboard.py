"""
Dashboard stats API — aggregate metrics for the frontend dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Application, CandidateProfile, Company, Job
from app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    """Aggregate dashboard statistics."""

    total_companies = (await db.execute(select(func.count(Company.id)).where(Company.is_active.is_(True)))).scalar_one()
    total_jobs = (await db.execute(select(func.count(Job.id)))).scalar_one()
    open_jobs = (await db.execute(select(func.count(Job.id)).where(Job.status.in_(["discovered", "open"])))).scalar_one()

    # Personalized stats only available after profile confirmation
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.is_confirmed.is_(True)).limit(1)
    )
    profile = profile_result.scalar_one_or_none()
    has_confirmed_profile = profile is not None

    # Application stats
    apps_awaiting = (
        await db.execute(
            select(func.count(Application.id)).where(Application.status == "ready_for_review")
        )
    ).scalar_one()

    apps_submitted = (
        await db.execute(
            select(func.count(Application.id)).where(Application.status == "applied")
        )
    ).scalar_one()

    apps_total = (await db.execute(select(func.count(Application.id)))).scalar_one()

    # Last discovery timestamp
    last_job = (await db.execute(
        select(Job.discovered_at).order_by(Job.discovered_at.desc()).limit(1)
    )).scalar_one_or_none()

    return DashboardStats(
        total_companies=total_companies,
        total_jobs=total_jobs,
        open_jobs=open_jobs,
        eligible_jobs=0,  # Populated after eligibility engine runs
        high_match_jobs=0,  # Populated after matching engine runs
        applications_awaiting_review=apps_awaiting,
        applications_submitted=apps_submitted,
        applications_total=apps_total,
        has_confirmed_profile=has_confirmed_profile,
        last_discovery_at=last_job,
    )
