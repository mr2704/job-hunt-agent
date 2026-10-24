"""
Jobs API router — GET /api/v1/jobs
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import Company, Job
from app.schemas.schemas import JobOut, JobWithCompanyOut, PagedResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=PagedResponse)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None, description="Search title or description"),
    company: str | None = Query(default=None, description="Filter by company name"),
    level: str | None = Query(default=None),
    department: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ats_platform: str | None = Query(default=None),
    sort_by: Literal["discovered_at", "posted_at", "title"] = Query(default="discovered_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse:
    stmt = (
        select(Job)
        .options(selectinload(Job.company))
        .join(Company, Job.company_id == Company.id)
    )

    if q:
        stmt = stmt.where(
            Job.title.ilike(f"%{q}%") | Job.description.ilike(f"%{q}%")
        )
    if company:
        stmt = stmt.where(Company.name.ilike(f"%{company}%"))
    if level:
        stmt = stmt.where(Job.level.ilike(f"%{level}%"))
    if department:
        stmt = stmt.where(Job.department.ilike(f"%{department}%"))
    if status:
        stmt = stmt.where(Job.status == status)
    if ats_platform:
        stmt = stmt.where(Job.ats_platform == ats_platform)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Sort
    sort_col = getattr(Job, sort_by, Job.discovered_at)
    if sort_order == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    # Paginate
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    jobs = (await db.execute(stmt)).scalars().all()

    return PagedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[JobWithCompanyOut.model_validate(j) for j in jobs],
    )


@router.get("/{job_id}", response_model=JobWithCompanyOut)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JobWithCompanyOut:
    result = await db.execute(
        select(Job).options(selectinload(Job.company)).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return JobWithCompanyOut.model_validate(job)
