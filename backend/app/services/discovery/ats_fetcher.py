"""
ATS detail fetcher — retrieves full job descriptions from external ATS platforms.

Supported static ATS platforms (no JS needed):
- Lever (jobs.lever.co) — static HTML with JSON-LD
- Greenhouse (boards.greenhouse.io) — static HTML
- Workable (apply.workable.com) — some require JS; Playwright fallback

Unsupported platforms fall back to returning None for description,
and the job is stored with what we have from BSM.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.+?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class ATSFetcher:
    """
    Fetches full job descriptions from external ATS platforms.
    Returns a dict with description, required_skills, etc. where available.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch(self, url: str, ats_platform: str) -> dict[str, Any]:
        """Dispatch to the appropriate ATS fetcher based on platform."""
        result: dict[str, Any] = {
            "description": None,
            "required_skills": None,
            "preferred_skills": None,
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "posted_at": None,
            "fetch_status": "not_attempted",
        }

        if not url:
            result["fetch_status"] = "no_url"
            return result

        try:
            if ats_platform == "lever":
                result.update(await self._fetch_lever(url))
            elif ats_platform == "greenhouse":
                result.update(await self._fetch_greenhouse(url))
            elif ats_platform == "workable":
                result.update(await self._fetch_workable(url))
            elif ats_platform in ("wellfound", "ashby"):
                result.update(await self._fetch_generic_with_jsonld(url))
            else:
                result.update(await self._fetch_generic_with_jsonld(url))
        except Exception as exc:
            logger.warning("ats_fetch_error", url=url, platform=ats_platform, error=str(exc))
            result["fetch_status"] = "error"
            result["fetch_error"] = str(exc)

        return result

    async def _get_html(self, url: str) -> str | None:
        try:
            resp = await self._client.get(
                url,
                timeout=settings.crawl_timeout_seconds,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text
            logger.warning("ats_non_200", url=url, status=resp.status_code)
            return None
        except httpx.RequestError as exc:
            logger.warning("ats_request_error", url=url, error=str(exc))
            return None

    async def _fetch_lever(self, url: str) -> dict[str, Any]:
        """Lever jobs expose a JSON endpoint: <url>.json"""
        json_url = url.rstrip("/") + ".json"
        try:
            resp = await self._client.get(json_url, timeout=settings.crawl_timeout_seconds)
            if resp.status_code == 200:
                data = resp.json()
                description_html = data.get("descriptionPlain") or data.get("description") or ""
                description = self._strip_html(description_html)
                lists = data.get("lists") or []
                required_skills: list[str] = []
                preferred_skills: list[str] = []
                for lst in lists:
                    text = lst.get("content", "")
                    label = (lst.get("text") or "").lower()
                    items = re.findall(r"<li>(.*?)</li>", text, re.DOTALL)
                    clean_items = [self._strip_html(i).strip() for i in items if i.strip()]
                    if any(k in label for k in ("require", "must", "qualif")):
                        required_skills.extend(clean_items)
                    elif any(k in label for k in ("prefer", "nice", "bonus", "plus")):
                        preferred_skills.extend(clean_items)
                return {
                    "description": description,
                    "required_skills": required_skills or None,
                    "preferred_skills": preferred_skills or None,
                    "employment_type": data.get("commitment"),
                    "posted_at": data.get("createdAt"),
                    "fetch_status": "success",
                }
        except Exception as exc:
            logger.debug("lever_json_failed", url=json_url, error=str(exc))

        # Fallback to HTML parse
        html = await self._get_html(url)
        return self._parse_generic_html(html) if html else {"fetch_status": "failed"}

    async def _fetch_greenhouse(self, url: str) -> dict[str, Any]:
        """Greenhouse has a structured HTML layout."""
        html = await self._get_html(url)
        if not html:
            return {"fetch_status": "failed"}
        result = self._parse_generic_html(html)
        # Try JSON-LD for salary
        result.update(self._parse_jsonld(html))
        return result

    async def _fetch_workable(self, url: str) -> dict[str, Any]:
        html = await self._get_html(url)
        if not html:
            return {"fetch_status": "failed"}
        return self._parse_generic_html(html)

    async def _fetch_generic_with_jsonld(self, url: str) -> dict[str, Any]:
        html = await self._get_html(url)
        if not html:
            return {"fetch_status": "failed"}
        result = self._parse_generic_html(html)
        result.update(self._parse_jsonld(html))
        return result

    # ── Parsers ──────────────────────────────────────────────────────────────

    def _parse_generic_html(self, html: str) -> dict[str, Any]:
        """Extract description text from common job-posting HTML patterns."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        # Remove nav, header, footer, scripts
        for tag in soup(["nav", "header", "footer", "script", "style", "noscript"]):
            tag.decompose()

        # Try common content selectors
        selectors = [
            "[class*='job-description']",
            "[class*='description']",
            "[id*='description']",
            "[class*='content']",
            "main",
            "article",
        ]
        content = None
        for sel in selectors:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                content = el.get_text(separator="\n", strip=True)
                break

        if not content:
            content = soup.get_text(separator="\n", strip=True)
            # Trim to reasonable length
            content = "\n".join(line for line in content.splitlines() if line.strip())

        return {
            "description": content[:8000] if content else None,
            "fetch_status": "success",
        }

    def _parse_jsonld(self, html: str) -> dict[str, Any]:
        """Extract structured data from JSON-LD schema.org JobPosting."""
        result: dict[str, Any] = {}
        for match in JSON_LD_RE.finditer(html):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    data = data[0] if data else {}
                if data.get("@type") != "JobPosting":
                    continue
                base_salary = data.get("baseSalary") or {}
                value = base_salary.get("value") or {}
                result["salary_min"] = value.get("minValue")
                result["salary_max"] = value.get("maxValue")
                result["salary_currency"] = base_salary.get("currency")
                result["employment_type"] = data.get("employmentType")
                result["posted_at"] = data.get("datePosted")
                if not result.get("description"):
                    result["description"] = self._strip_html(data.get("description") or "")
            except Exception:
                continue
        return result

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags, returning plain text."""
        clean = re.sub(r"<[^>]+>", " ", html or "")
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()
