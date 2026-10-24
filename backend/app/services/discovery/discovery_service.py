"""
Discovery service — orchestrates BSM crawling, normalization,
deduplication, and database persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Company, Job
from app.services.discovery.bsm_adapter import BSMAdapter
from app.services.discovery.ats_fetcher import ATSFetcher
import httpx

logger = structlog.get_logger(__name__)


class DiscoveryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_discovery(
        self,
        max_companies: int | None = None,
        fetch_jd: bool = False,
    ) -> dict[str, int]:
        """
        Full discovery pipeline:
          1. Fetch all hiring companies + job listings from BSM.
          2. Upsert companies into DB.
          3. Upsert jobs into DB.
          4. Optionally fetch full JDs from ATS.

        Returns a summary dict with counts.
        """
        logger.info("discovery_started", max_companies=max_companies)
        stats = {
            "companies_found": 0,
            "companies_new": 0,
            "jobs_found": 0,
            "jobs_new": 0,
            "jobs_updated": 0,
            "jds_fetched": 0,
            "errors": 0,
        }

        async with BSMAdapter() as adapter:
            companies_raw, jobs_raw = await adapter.fetch_all_jobs(max_companies=max_companies)

        stats["companies_found"] = len(companies_raw)
        stats["jobs_found"] = len(jobs_raw)

        # Upsert companies
        company_id_map: dict[str, uuid.UUID] = {}
        for c in companies_raw:
            try:
                db_company = await self._upsert_company(c)
                company_id_map[c["slug"]] = db_company.id
                if db_company.discovered_at and (datetime.utcnow() - db_company.discovered_at).seconds < 60:
                    stats["companies_new"] += 1
            except Exception as exc:
                logger.error("company_upsert_error", slug=c.get("slug"), error=str(exc))
                stats["errors"] += 1

        # Upsert jobs
        jobs_to_enrich: list[tuple[uuid.UUID, str, str]] = []  # (job_id, url, ats_platform)
        for j in jobs_raw:
            try:
                slug = j.get("company_slug", "")
                company_id = company_id_map.get(slug)
                if not company_id:
                    continue

                db_job, is_new = await self._upsert_job(j, company_id)
                if is_new:
                    stats["jobs_new"] += 1
                else:
                    stats["jobs_updated"] += 1

                if fetch_jd and j.get("original_url") and not db_job.description:
                    jobs_to_enrich.append((db_job.id, j["original_url"], j.get("ats_platform", "unknown")))

            except Exception as exc:
                logger.error("job_upsert_error", title=j.get("title"), error=str(exc))
                stats["errors"] += 1

        await self.db.commit()

        # Enrich with full JDs
        if jobs_to_enrich:
            async with httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobDiscoveryBot/1.0)"},
                follow_redirects=True,
            ) as client:
                fetcher = ATSFetcher(client)
                for job_id, url, platform in jobs_to_enrich:
                    try:
                        details = await fetcher.fetch(url, platform)
                        if details.get("description"):
                            await self._update_job_description(job_id, details)
                            stats["jds_fetched"] += 1
                    except Exception as exc:
                        logger.warning("jd_fetch_error", job_id=str(job_id), error=str(exc))

            await self.db.commit()

        logger.info("discovery_complete", **stats)
        return stats

    # ── DB operations ────────────────────────────────────────────────────────

    async def _upsert_company(self, data: dict[str, Any]) -> Company:
        slug = data["slug"]
        result = await self.db.execute(select(Company).where(Company.slug == slug))
        company = result.scalar_one_or_none()

        if company is None:
            company = Company(
                slug=slug,
                name=data.get("name", ""),
                description=data.get("description"),
                sector=data.get("sector"),
                area=data.get("area"),
                founded_year=data.get("founded_year"),
                website=data.get("website"),
                logo_url=data.get("logo_url"),
                funding_stage=data.get("funding_stage"),
                bsm_url=data.get("bsm_url"),
                extra_data=data.get("raw_data"),
                discovered_at=datetime.utcnow(),
                last_verified_at=datetime.utcnow(),
            )
            self.db.add(company)
        else:
            # Update mutable fields
            company.name = data.get("name") or company.name
            company.description = data.get("description") or company.description
            company.sector = data.get("sector") or company.sector
            company.area = data.get("area") or company.area
            company.website = data.get("website") or company.website
            company.logo_url = data.get("logo_url") or company.logo_url
            company.funding_stage = data.get("funding_stage") or company.funding_stage
            company.last_verified_at = datetime.utcnow()
            company.is_active = True

        await self.db.flush()
        return company

    async def _upsert_job(
        self,
        data: dict[str, Any],
        company_id: uuid.UUID,
    ) -> tuple[Job, bool]:
        """Upsert a job record. Returns (job, is_new)."""
        external_id = data.get("external_job_id")
        ats_platform = data.get("ats_platform", "unknown")

        # Try to find existing by external_job_id + ats_platform
        existing = None
        if external_id and ats_platform and ats_platform != "unknown":
            result = await self.db.execute(
                select(Job).where(
                    Job.external_job_id == external_id,
                    Job.ats_platform == ats_platform,
                )
            )
            existing = result.scalar_one_or_none()

        # Fallback: find by title + company + level (fuzzy dedup)
        if not existing:
            result = await self.db.execute(
                select(Job).where(
                    Job.company_id == company_id,
                    Job.title == data["title"],
                    Job.level == data.get("level"),
                )
            )
            existing = result.scalar_one_or_none()

        is_new = existing is None

        if is_new:
            job = Job(
                company_id=company_id,
                title=data["title"],
                department=data.get("department"),
                level=data.get("level"),
                employment_type=data.get("employment_type"),
                location=data.get("location"),
                remote_policy=data.get("remote_policy"),
                description=data.get("description"),
                required_skills=data.get("required_skills"),
                preferred_skills=data.get("preferred_skills"),
                bsm_url=data.get("bsm_url"),
                original_url=data.get("original_url"),
                application_url=data.get("application_url"),
                ats_platform=ats_platform,
                external_job_id=external_id,
                posted_at=self._parse_datetime(data.get("posted_at")),
                discovered_at=datetime.utcnow(),
                last_verified_at=datetime.utcnow(),
                status="discovered",
                extraction_confidence=data.get("extraction_confidence"),
                raw_data=data.get("raw_data"),
            )
            self.db.add(job)
        else:
            # Update verification timestamp and mutable fields
            existing.last_verified_at = datetime.utcnow()
            existing.status = "open"
            existing.application_url = data.get("application_url") or existing.application_url
            existing.original_url = data.get("original_url") or existing.original_url
            job = existing

        await self.db.flush()
        return job, is_new

    async def _update_job_description(
        self,
        job_id: uuid.UUID,
        details: dict[str, Any],
    ) -> None:
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.description = details.get("description") or job.description
            job.required_skills = details.get("required_skills") or job.required_skills
            job.preferred_skills = details.get("preferred_skills") or job.preferred_skills
            job.employment_type = details.get("employment_type") or job.employment_type
            job.salary_min = details.get("salary_min") or job.salary_min
            job.salary_max = details.get("salary_max") or job.salary_max
            job.salary_currency = details.get("salary_currency") or job.salary_currency
        await self.db.flush()

    @staticmethod
    def _parse_datetime(v: str | None) -> datetime | None:
        if not v:
            return None
        try:
            return datetime.fromisoformat(v.rstrip("Z"))
        except ValueError:
            return None
