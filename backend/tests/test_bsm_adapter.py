"""
Tests for the BSM source adapter.

These tests use HTTP mocking — no real network requests are made.
They validate extraction logic against captured real page structure.
"""
from __future__ import annotations

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from app.services.discovery.bsm_adapter import BSMAdapter, NEXT_DATA_RE


# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_NEXT_DATA_HIRING = {
    "props": {
        "pageProps": {
            "startups": [
                {
                    "slug": "acceldata",
                    "name": "Acceldata",
                    "description": "Data observability platform",
                    "sector": "SaaS",
                    "area": "HSR Layout",
                    "founded": 2018,
                    "website": "https://www.acceldata.io",
                    "logo": "https://cdn.example.com/acceldata.png",
                    "stage": "Series C+",
                    "openRoles": 4,
                },
                {
                    "slug": "atlan",
                    "name": "Atlan",
                    "description": "Active metadata and data-governance platform",
                    "sector": "SaaS",
                    "area": "HSR Layout",
                    "founded": 2018,
                    "website": "https://atlan.com",
                    "openRoles": 4,
                },
            ]
        }
    },
    "buildId": "test-build-id-123",
    "page": "/",
}

MOCK_NEXT_DATA_COMPANY = {
    "props": {
        "pageProps": {
            "company": {
                "slug": "acceldata",
                "name": "Acceldata",
                "description": "Data observability platform",
                "sector": "SaaS",
                "area": "HSR Layout",
                "founded": 2018,
                "website": "https://www.acceldata.io",
                "stage": "Series C+",
            },
            "jobs": [
                {
                    "title": "Staff Product Support Engineer - Cloud Support",
                    "department": "Sales & Marketing",
                    "level": "Lead",
                    "url": "https://jobs.lever.co/acceldata/abc123",
                    "posted": "2024-10-13",
                },
                {
                    "title": "Senior Engineering Manager",
                    "department": "Engineering",
                    "level": "Lead",
                    "url": "https://jobs.lever.co/acceldata/def456",
                    "posted": "2024-08-13",
                },
            ],
        }
    },
    "buildId": "test-build-id-123",
    "page": "/company/[slug]",
}


def _make_html_with_next_data(data: dict) -> str:
    json_str = json.dumps(data)
    return f'<html><head></head><body><script id="__NEXT_DATA__" type="application/json">{json_str}</script></body></html>'


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestNextDataExtraction:
    def test_extracts_valid_next_data(self):
        html = _make_html_with_next_data(MOCK_NEXT_DATA_HIRING)
        adapter = BSMAdapter.__new__(BSMAdapter)
        result = adapter._extract_next_data(html)
        assert result is not None
        assert result["buildId"] == "test-build-id-123"

    def test_returns_none_for_missing_next_data(self):
        html = "<html><body><p>No Next.js here</p></body></html>"
        adapter = BSMAdapter.__new__(BSMAdapter)
        result = adapter._extract_next_data(html)
        assert result is None

    def test_returns_none_for_malformed_json(self):
        html = '<script id="__NEXT_DATA__" type="application/json">{invalid json}</script>'
        adapter = BSMAdapter.__new__(BSMAdapter)
        result = adapter._extract_next_data(html)
        assert result is None


class TestATSDetection:
    def test_detects_lever(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        assert adapter._detect_ats("https://jobs.lever.co/company/abc123") == "lever"

    def test_detects_greenhouse(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        assert adapter._detect_ats("https://boards.greenhouse.io/company/jobs/123") == "greenhouse"

    def test_detects_workable(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        assert adapter._detect_ats("https://apply.workable.com/company/j/ABC123") == "workable"

    def test_returns_unknown_for_unrecognized(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        assert adapter._detect_ats("https://example-startup.com/careers/job-123") == "unknown"


class TestNormalization:
    def test_normalizes_company(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        raw = MOCK_NEXT_DATA_HIRING["props"]["pageProps"]["startups"][0]
        result = adapter._normalize_company(raw)
        assert result is not None
        assert result["slug"] == "acceldata"
        assert result["name"] == "Acceldata"
        assert result["sector"] == "SaaS"
        assert result["founded_year"] == 2018

    def test_normalize_company_missing_slug_returns_none(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        result = adapter._normalize_company({})
        assert result is None

    def test_normalizes_job(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        raw = MOCK_NEXT_DATA_COMPANY["props"]["pageProps"]["jobs"][0]
        result = adapter._normalize_job(raw, company_slug="acceldata")
        assert result is not None
        assert result["title"] == "Staff Product Support Engineer - Cloud Support"
        assert result["ats_platform"] == "lever"
        assert result["application_url"] == "https://jobs.lever.co/acceldata/abc123"

    def test_normalize_job_empty_title_returns_none(self):
        adapter = BSMAdapter.__new__(BSMAdapter)
        result = adapter._normalize_job({"title": ""}, company_slug="test")
        assert result is None


class TestExternalIdExtraction:
    def test_extracts_lever_uuid(self):
        url = "https://jobs.lever.co/acceldata/abcd1234-ef56-7890-abcd-ef1234567890"
        result = BSMAdapter._extract_external_id(url)
        assert result == "abcd1234-ef56-7890-abcd-ef1234567890"

    def test_extracts_greenhouse_id(self):
        url = "https://boards.greenhouse.io/company/jobs/7654321"
        result = BSMAdapter._extract_external_id(url)
        assert result == "7654321"

    def test_returns_none_for_unknown(self):
        url = "https://example.com/jobs/some-role"
        result = BSMAdapter._extract_external_id(url)
        assert result is None


@pytest.mark.asyncio
class TestBSMAdapterIntegration:
    async def test_fetch_hiring_companies_parses_correctly(self):
        """Test that fetch_hiring_companies parses __NEXT_DATA__ correctly from mocked HTML."""
        html = _make_html_with_next_data(MOCK_NEXT_DATA_HIRING)

        adapter = BSMAdapter()
        adapter._rate_limiter = AsyncMock()
        adapter._rate_limiter.acquire = AsyncMock()

        import httpx
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        companies = await adapter.fetch_hiring_companies()
        assert len(companies) == 2
        assert companies[0]["slug"] == "acceldata"
        assert companies[1]["slug"] == "atlan"

    async def test_fetch_company_jobs_returns_normalized_jobs(self):
        html = _make_html_with_next_data(MOCK_NEXT_DATA_COMPANY)

        adapter = BSMAdapter()
        adapter._rate_limiter = AsyncMock()
        adapter._rate_limiter.acquire = AsyncMock()

        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        company, jobs = await adapter.fetch_company_jobs("acceldata")
        assert company is not None
        assert company["slug"] == "acceldata"
        assert len(jobs) == 2
        assert jobs[0]["ats_platform"] == "lever"
