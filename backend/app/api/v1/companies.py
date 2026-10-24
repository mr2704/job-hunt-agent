"""
Companies API router.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Company
from app.schemas.schemas import CompanyOut, PagedResponse

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=PagedResponse)
async def list_companies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse:
    stmt = select(Company).where(Company.is_active.is_(True))

    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    if sector:
        stmt = stmt.where(Company.sector.ilike(f"%{sector}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Company.name.asc()).offset((page - 1) * page_size).limit(page_size)
    companies = (await db.execute(stmt)).scalars().all()

    return PagedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CompanyOut.model_validate(c) for c in companies],
    )


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CompanyOut:
    from fastapi import HTTPException
    result = await db.execute(select(Company).where(Company.id == company_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyOut.model_validate(c)
