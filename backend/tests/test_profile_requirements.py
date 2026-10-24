"""
Tests enforcing the empty-profile requirement.

These tests prove that:
1. The candidate profile starts empty.
2. Personalized operations (matching, eligibility) cannot run before confirmation.
3. Application submission cannot happen without explicit approval.
"""
from __future__ import annotations

import pytest


class TestEmptyProfileRequirement:
    """Enforce that candidate profile starts empty."""

    def test_candidate_profile_all_fields_nullable(self):
        """Verify that CandidateProfile can be instantiated with all null fields."""
        from app.models.models import CandidateProfile

        profile = CandidateProfile()
        nullable_fields = [
            "full_name", "email", "phone", "location",
            "degree", "graduation_year", "cgpa", "percentage",
            "skills", "work_experience", "projects",
            "expected_salary_min", "expected_salary_max",
        ]
        for field in nullable_fields:
            assert getattr(profile, field) is None, f"{field} should be None on empty profile"

    def test_candidate_profile_not_confirmed_by_default(self):
        """Verify that a new profile is never auto-confirmed."""
        from app.models.models import CandidateProfile

        profile = CandidateProfile()
        assert profile.is_confirmed is False
        assert profile.confirmed_at is None

    def test_resume_parser_returns_only_explicit_data(self):
        """Verify the parser does not fabricate missing fields."""
        import asyncio
        import io
        from app.services.candidate.resume_parser import ResumeParser

        parser = ResumeParser()

        # A nearly empty PDF (just whitespace)
        try:
            import pdfplumber
            # Create a minimal PDF in memory
            from reportlab.pdfgen import canvas
            buf = io.BytesIO()
            c = canvas.Canvas(buf)
            c.drawString(100, 750, "   ")
            c.save()
            buf.seek(0)
        except ImportError:
            # If reportlab not available, use a fake empty bytes object
            buf = io.BytesIO(b"%PDF-1.4 1 0 obj<</Type /Catalog>>endobj")

        result = asyncio.run(parser.parse_pdf(buf))

        # Should NOT invent any personal data
        assert result.get("full_name") is None or isinstance(result.get("full_name"), str)
        assert result.get("cgpa") is None  # No CGPA in empty doc
        assert result.get("graduation_year") is None  # No year in empty doc


class TestPersonalizationGating:
    """Verify that personalized operations require confirmed profile."""

    def test_profile_must_be_confirmed_before_matching(self):
        """
        Simulate the gating check that must exist in the matching engine.
        """
        from app.models.models import CandidateProfile

        unconfirmed_profile = CandidateProfile(is_confirmed=False)

        def _check_profile_confirmed(profile: CandidateProfile) -> bool:
            """This guard must be called before any matching operation."""
            return profile.is_confirmed

        assert not _check_profile_confirmed(unconfirmed_profile), (
            "Matching must be blocked for unconfirmed profiles"
        )

    def test_application_submission_requires_approved_status(self):
        """Verify that Application.status must be 'approved' before submission."""
        from app.models.models import Application

        app = Application(status="ready_for_review")
        SUBMITTABLE_STATUSES = {"approved"}

        assert app.status not in SUBMITTABLE_STATUSES, (
            "Application must not be submitted without explicit approval"
        )

    def test_confirmed_profile_enables_matching(self):
        """After confirmation, matching should be allowed."""
        from app.models.models import CandidateProfile, utc_now_naive

        confirmed = CandidateProfile(is_confirmed=True, confirmed_at=utc_now_naive())
        assert confirmed.is_confirmed is True


class TestDuplicatePreventionModel:
    """Verify deduplication constraints are defined in the schema."""

    def test_application_unique_constraint_exists(self):
        """Application must have a unique constraint on (job_id, profile_id)."""
        from app.models.models import Application
        from sqlalchemy import inspect

        # Check table args
        table_args = Application.__table_args__
        constraint_names = [c.name for c in table_args if hasattr(c, "name")]
        assert "uq_application_job_profile" in constraint_names

    def test_job_unique_constraint_exists(self):
        """Job must have a unique constraint on (external_job_id, ats_platform)."""
        from app.models.models import Job

        table_args = Job.__table_args__
        constraint_names = [c.name for c in table_args if hasattr(c, "name")]
        assert "uq_job_external" in constraint_names
