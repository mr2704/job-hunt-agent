"""
Bangalore Startup Map — source adapter.

Extraction strategy (confirmed via Phase 0 investigation):
  1. Fetch the hiring page (?hiring=1) via HTTP.
  2. Parse the embedded <script id="__NEXT_DATA__"> JSON — no JS rendering needed.
  3. The pageProps contains a 'startups' array with company slugs.
  4. For each slug, fetch /company/{slug} and extract the 'jobs' array.
  5. Normalize to the canonical Job data model.
  6. Follow external ATS URLs to fetch full job descriptions.

Rate limiting: 1 req/sec by default. Polite crawling only.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

BSM_BASE = settings.bsm_base_url
HIRING_URL = f"{BSM_BASE}/?hiring=1"
COMPANY_URL = f"{BSM_BASE}/company/{{slug}}"

# Known ATS platforms and their URL patterns
ATS_PATTERNS: dict[str, str] = {
    "lever.co": "lever",
    "jobs.lever.co": "lever",
    "greenhouse.io": "greenhouse",
    "boards.greenhouse.io": "greenhouse",
    "workable.com": "workable",
    "apply.workable.com": "workable",
    "linkedin.com/jobs": "linkedin",
    "naukri.com": "naukri",
    "indeed.com": "indeed",
    "instahyre.com": "instahyre",
    "internshala.com": "internshala",
    "smartrecruiters.com": "smartrecruiters",
    "ashbyhq.com": "ashby",
    "jobs.ashbyhq.com": "ashby",
    "wellfound.com": "wellfound",
    "angel.co": "wellfound",
}

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', re.DOTALL)


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, rps: float) -> None:
        self.min_interval = 1.0 / rps
        self._last: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class BSMAdapter:
    """
    Discovers job listings from Bangalore Startup Map.

    Usage:
        async with BSMAdapter() as adapter:
            companies = await adapter.fetch_hiring_companies()
            for c in companies:
                jobs = await adapter.fetch_company_jobs(c['slug'])
    """

    def __init__(self) -> None:
        self._rate_limiter = RateLimiter(settings.crawl_rate_limit_rps)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BSMAdapter":
        self._client = httpx.AsyncClient(
            timeout=settings.crawl_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; JobDiscoveryBot/1.0; "
                    "+https://github.com/startup-job-agent)"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _get(self, url: str, retries: int = 0) -> str | None:
        """Fetch a URL respecting rate limits, with bounded retries."""
        await self._rate_limiter.acquire()
        for attempt in range(retries + 1):
            try:
                assert self._client is not None
                resp = await self._client.get(url)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (429, 503) and attempt < retries:
                    wait = 2 ** attempt * 2
                    logger.warning("rate_limited", url=url, attempt=attempt, wait=wait)
                    await asyncio.sleep(wait)
                else:
                    logger.error("http_error", url=url, status=exc.response.status_code)
                    return None
            except httpx.RequestError as exc:
                logger.error("request_error", url=url, error=str(exc), attempt=attempt)
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None
        return None

    @staticmethod
    def _extract_next_data(html: str) -> dict[str, Any] | None:
        """Extract and parse the __NEXT_DATA__ JSON embedded in Next.js SSR pages."""
        match = NEXT_DATA_RE.search(html)
        if not match:
            logger.warning("next_data_not_found")
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.error("next_data_parse_error", error=str(exc))
            return None

    @staticmethod
    def _detect_ats(url: str) -> str:
        """Identify the ATS platform from a job URL."""
        try:
            host = urlparse(url).netloc.lower().lstrip("www.")
            for pattern, name in ATS_PATTERNS.items():
                if host == pattern or host.endswith(f".{pattern}"):
                    return name
        except Exception:
            pass
        return "unknown"

    # ── Public methods ──────────────────────────────────────────────────────

    async def fetch_hiring_companies(self) -> list[dict[str, Any]]:
        """
        Fetch the list of all companies currently hiring from BSM.
        Returns a list of normalized company dicts.
        """
        logger.info("fetching_hiring_page", url=HIRING_URL)
        html = await self._get(HIRING_URL, retries=settings.crawl_max_retries)
        if not html:
            logger.error("failed_to_fetch_hiring_page")
            return []

        next_data = self._extract_next_data(html)
        if not next_data:
            return []

        page_props = next_data.get("props", {}).get("pageProps", {})

        # BSM uses 'startups' key for the company list on the hiring page
        raw_companies = (
            page_props.get("startups")
            or page_props.get("companies")
            or []
        )

        companies = []
        for raw in raw_companies:
            company = self._normalize_company(raw)
            if company:
                companies.append(company)

        logger.info("discovered_companies", count=len(companies))
        return companies

    async def fetch_company_jobs(self, slug: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """
        Fetch the company detail page and extract all job listings.
        Returns (company_data, jobs_list).
        """
        url = COMPANY_URL.format(slug=slug)
        logger.info("fetching_company_page", slug=slug, url=url)

        html = await self._get(url, retries=settings.crawl_max_retries)
        if not html:
            logger.warning("failed_to_fetch_company", slug=slug)
            return None, []

        next_data = self._extract_next_data(html)
        if not next_data:
            return None, []

        page_props = next_data.get("props", {}).get("pageProps", {})

        raw_company = page_props.get("company") or {}
        raw_jobs = page_props.get("jobs") or []

        company = self._normalize_company(raw_company, slug=slug, bsm_url=url)

        jobs = []
        for raw_job in raw_jobs:
            job = self._normalize_job(raw_job, company_slug=slug)
            if job:
                jobs.append(job)

        logger.info("discovered_jobs", slug=slug, count=len(jobs))
        return company, jobs

    async def fetch_all_jobs(self, max_companies: int | None = None) -> tuple[list[dict], list[dict]]:
        """
        Full discovery: fetch all hiring companies and their jobs.
        Returns (companies, jobs).
        """
        companies = await self.fetch_hiring_companies()
        if max_companies:
            companies = companies[:max_companies]

        all_jobs: list[dict] = []
        seen_slugs: set[str] = set()

        for company_summary in companies:
            slug = company_summary.get("slug")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            company_detail, jobs = await self.fetch_company_jobs(slug)
            if company_detail:
                # Merge detail into summary
                company_summary.update(
                    {k: v for k, v in company_detail.items() if v is not None}
                )

            all_jobs.extend(jobs)

        logger.info("discovery_complete", companies=len(companies), jobs=len(all_jobs))
        return companies, all_jobs

    # ── Normalizers ─────────────────────────────────────────────────────────

    def _normalize_company(
        self,
        raw: dict[str, Any],
        slug: str | None = None,
        bsm_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Normalize a raw company dict from BSM __NEXT_DATA__ to our schema."""
        if not raw:
            return None

        slug = slug or raw.get("slug") or raw.get("id") or ""
        if not slug:
            return None

        return {
            "slug": str(slug).lower().strip(),
            "name": raw.get("name") or raw.get("title") or "",
            "description": raw.get("description") or raw.get("about") or None,
            "sector": raw.get("sector") or raw.get("category") or None,
            "area": raw.get("area") or raw.get("location") or None,
            "founded_year": self._to_int(raw.get("founded") or raw.get("foundedYear")),
            "website": raw.get("website") or raw.get("url") or None,
            "logo_url": raw.get("logo") or raw.get("logoUrl") or None,
            "funding_stage": raw.get("stage") or raw.get("fundingStage") or None,
            "bsm_url": bsm_url or f"{BSM_BASE}/company/{slug}",
            "open_roles_count": self._to_int(raw.get("openRoles") or raw.get("jobCount")),
            "raw_data": raw,
        }

    def _normalize_job(
        self,
        raw: dict[str, Any],
        company_slug: str,
    ) -> dict[str, Any] | None:
        """Normalize a raw job dict from BSM __NEXT_DATA__ to our schema."""
        if not raw:
            return None

        title = raw.get("title") or raw.get("name") or ""
        if not title:
            return None

        # External application URL
        app_url = (
            raw.get("url")
            or raw.get("applyUrl")
            or raw.get("applicationUrl")
            or raw.get("externalUrl")
            or None
        )

        # External job ID (from URL if possible)
        external_id = raw.get("id") or raw.get("externalId") or None
        if not external_id and app_url:
            # Try extracting ID from ATS URL
            external_id = self._extract_external_id(app_url)

        ats = self._detect_ats(app_url) if app_url else "unknown"

        # Posted date
        posted_raw = raw.get("postedAt") or raw.get("datePosted") or raw.get("posted") or None
        posted_at = self._parse_date(posted_raw)

        return {
            "title": title.strip(),
            "department": raw.get("department") or raw.get("field") or None,
            "level": raw.get("level") or raw.get("seniority") or None,
            "employment_type": raw.get("type") or raw.get("employmentType") or None,
            "location": raw.get("location") or "Bengaluru",
            "remote_policy": raw.get("remote") or raw.get("workMode") or None,
            "description": raw.get("description") or None,  # Often null on BSM; fetch from ATS
            "required_skills": raw.get("requiredSkills") or None,
            "preferred_skills": raw.get("preferredSkills") or None,
            "bsm_url": f"{BSM_BASE}/company/{company_slug}",
            "original_url": app_url,
            "application_url": app_url,
            "ats_platform": ats,
            "external_job_id": str(external_id) if external_id else None,
            "posted_at": posted_at.isoformat() if posted_at else None,
            "company_slug": company_slug,
            "extraction_confidence": 0.8 if app_url else 0.5,
            "raw_data": raw,
        }

    # ── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_int(v: Any) -> int | None:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_external_id(url: str) -> str | None:
        """Try to extract a job ID from common ATS URL patterns."""
        # Lever: jobs.lever.co/company/UUID
        m = re.search(r"lever\.co/[^/]+/([a-f0-9\-]{36})", url)
        if m:
            return m.group(1)
        # Greenhouse: boards.greenhouse.io/company/jobs/12345
        m = re.search(r"greenhouse\.io/[^/]+/jobs/(\d+)", url)
        if m:
            return m.group(1)
        # Workable: apply.workable.com/company/j/XXXXXX
        m = re.search(r"workable\.com/[^/]+/j/([A-Z0-9]+)", url)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%d %b %Y",
            "%b %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(str(raw), fmt)
            except ValueError:
                continue
        return None
