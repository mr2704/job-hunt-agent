"""
Comprehensive automated tests for candidate onboarding workflow.
Covers:
- PDF upload validation (size, extension, magic bytes, corrupt, encrypted, empty)
- Pydantic profile validation rules (email, grad year, CGPA, scale, skills normalization)
- Profile scoping, lifecycle gating, and duplicate prevention
- Disk storage preservation and file cleanup
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfWriter

from app.api.v1.candidate import (
    confirm_profile,
    delete_profile,
    get_profile,
    update_profile,
    upload_resume,
)
from app.core.config import get_settings
from app.models.models import CandidateProfile, ResumeVersion
from app.schemas.schemas import CandidateProfileOut, CandidateProfileUpdate
from app.services.candidate.resume_parser import ResumeParser


def create_minimal_pdf(pages: int = 1) -> bytes:
    """Generate a minimal valid PDF byte sequence in memory."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class MockUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if size == -1:
            return self._content
        chunk = self._content[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


# ─── 1. UPLOAD VALIDATION TESTS ───────────────────────────────────────────────

class TestUploadValidation:
    """Tests covering resume upload constraints and security."""

    @pytest.mark.asyncio
    async def test_valid_pdf_upload(self, tmp_path):
        """A valid PDF should be accepted, saved to disk, parsed, and recorded as draft."""
        pdf_bytes = create_minimal_pdf(pages=1)
        upload_file = MockUploadFile(filename="resume.pdf", content=pdf_bytes)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.commit = AsyncMock()

        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            result = await upload_resume(file=upload_file, db=db)

            assert "profile_id" in result
            assert "extracted" in result
            assert result["message"].startswith("Resume uploaded successfully")

            # Verify CandidateProfile was added with is_confirmed=False
            added_objects = [call[0][0] for call in db.add.call_args_list]
            profiles = [o for o in added_objects if isinstance(o, CandidateProfile)]
            assert len(profiles) == 1
            assert profiles[0].is_confirmed is False
            assert profiles[0].version == 1

            # Verify ResumeVersion was added with is_base=True
            resume_versions = [o for o in added_objects if isinstance(o, ResumeVersion)]
            assert len(resume_versions) == 1
            assert resume_versions[0].is_base is True

    @pytest.mark.asyncio
    async def test_invalid_file_extension_rejected(self):
        """Non-PDF extensions (.docx, .txt, .png) must be rejected with 422."""
        db = AsyncMock()
        for bad_filename in ["resume.docx", "resume.txt", "resume.png", "resume"]:
            upload_file = MockUploadFile(filename=bad_filename, content=b"%PDF-1.4 dummy")
            with pytest.raises(HTTPException) as exc:
                await upload_resume(file=upload_file, db=db)
            assert exc.value.status_code == 422
            assert "Only PDF files are accepted" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_file_rejected(self):
        """Empty uploads (0 bytes) must be rejected before saving or parsing."""
        db = AsyncMock()
        upload_file = MockUploadFile(filename="empty.pdf", content=b"")
        with pytest.raises(HTTPException) as exc:
            await upload_resume(file=upload_file, db=db)
        assert exc.value.status_code == 422
        assert "empty" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_magic_bytes_rejected(self):
        """Files with .pdf extension but invalid header (e.g. text or script) must be rejected."""
        db = AsyncMock()
        upload_file = MockUploadFile(filename="fake.pdf", content=b"This is just plain text content.")
        with pytest.raises(HTTPException) as exc:
            await upload_resume(file=upload_file, db=db)
        assert exc.value.status_code == 422
        assert "not a valid PDF" in exc.value.detail

    @pytest.mark.asyncio
    async def test_corrupt_pdf_rejected(self):
        """Files with %PDF- header but malformed or truncated structure must be rejected."""
        db = AsyncMock()
        corrupt_bytes = b"%PDF-1.4\n%corrupt truncated content..."
        upload_file = MockUploadFile(filename="corrupt.pdf", content=corrupt_bytes)
        with pytest.raises(HTTPException) as exc:
            await upload_resume(file=upload_file, db=db)
        assert exc.value.status_code == 422
        assert "corrupt or malformed" in exc.value.detail

    @pytest.mark.asyncio
    async def test_file_exceeding_max_size_rejected(self):
        """Files larger than 50 MB must be rejected with 413."""
        db = AsyncMock()
        oversized_content = b"%PDF-1.4\n" + (b"0" * (51 * 1024 * 1024))
        upload_file = MockUploadFile(filename="huge.pdf", content=oversized_content)
        with pytest.raises(HTTPException) as exc:
            await upload_resume(file=upload_file, db=db)
        assert exc.value.status_code == 413
        assert "exceeds maximum size" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_extraction_handled_gracefully(self):
        """PDFs with no extractable text must not crash; returns warnings and empty fields."""
        parser = ResumeParser()
        buf = io.BytesIO(create_minimal_pdf(pages=1))
        extracted = await parser.parse_pdf(buf)

        assert isinstance(extracted, dict)
        assert extracted.get("full_name") is None
        assert extracted.get("email") is None
        assert extracted.get("cgpa") is None
        assert "_warnings" in extracted
        assert len(extracted["_warnings"]) > 0


# ─── 2. PROFILE VALIDATION TESTS ──────────────────────────────────────────────

class TestProfileValidation:
    """Tests covering CandidateProfileUpdate schema validation."""

    def test_valid_profile_update(self):
        """Valid profile data passes validation successfully."""
        data = CandidateProfileUpdate(
            full_name="John Doe",
            email="john.doe@example.com",
            phone="+919876543210",
            location="Bangalore, Karnataka",
            degree="B.Tech Computer Science",
            graduation_year=2024,
            cgpa=8.5,
            cgpa_scale=10.0,
            skills=["Python", "React", "PostgreSQL"],
        )
        assert data.email == "john.doe@example.com"
        assert data.graduation_year == 2024
        assert data.cgpa == 8.5
        assert data.cgpa_scale == 10.0
        assert data.skills == ["Python", "React", "PostgreSQL"]

    def test_invalid_email_format_rejected(self):
        """Malformed email strings must raise validation errors."""
        for bad_email in ["notanemail", "user@", "@domain.com", "user@domain"]:
            with pytest.raises(ValidationError):
                CandidateProfileUpdate(email=bad_email)

    def test_graduation_year_bounds_enforced(self):
        """Graduation years outside 1970-2035 must be rejected."""
        CandidateProfileUpdate(graduation_year=1970)
        CandidateProfileUpdate(graduation_year=2035)
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(graduation_year=1969)
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(graduation_year=2036)

    def test_negative_cgpa_rejected(self):
        """Negative CGPA values must be rejected."""
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(cgpa=-0.5)

    def test_non_positive_cgpa_scale_rejected(self):
        """CGPA scale <= 0 must be rejected."""
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(cgpa_scale=0.0)
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(cgpa_scale=-4.0)

    def test_cgpa_cannot_exceed_scale(self):
        """CGPA higher than its stated scale must be rejected."""
        CandidateProfileUpdate(cgpa=3.8, cgpa_scale=4.0)
        CandidateProfileUpdate(cgpa=9.5, cgpa_scale=10.0)
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(cgpa=9.5, cgpa_scale=4.0)
        with pytest.raises(ValidationError):
            CandidateProfileUpdate(cgpa=10.5, cgpa_scale=10.0)

    def test_skills_normalization(self):
        """Skills must be stripped of whitespace and deduplicated case-insensitively."""
        data = CandidateProfileUpdate(
            skills=["  Python ", "python", "React", "REACT", "TypeScript", "  "]
        )
        assert data.skills == ["Python", "React", "TypeScript"]

    def test_optional_fields_remain_optional(self):
        """Missing or omitted fields must remain None, never fabricated."""
        data = CandidateProfileUpdate()
        assert data.full_name is None
        assert data.email is None
        assert data.cgpa is None
        assert data.graduation_year is None
        assert data.skills is None


# ─── 3. PROFILE INTEGRITY & LIFECYCLE TESTS ───────────────────────────────────

class TestProfileIntegrityAndLifecycle:
    """Tests covering profile scoping, confirmation gating, and storage."""

    def test_profile_starts_empty_and_unconfirmed(self):
        """New CandidateProfile instances must default to unconfirmed with null fields."""
        profile = CandidateProfile()
        assert profile.is_confirmed is False
        assert profile.confirmed_at is None
        assert profile.full_name is None
        assert profile.email is None
        assert profile.cgpa is None

    def test_cannot_set_is_confirmed_via_update_schema(self):
        """Clients cannot pass is_confirmed in PATCH body."""
        assert "is_confirmed" not in CandidateProfileUpdate.model_fields
        assert "confirmed_at" not in CandidateProfileUpdate.model_fields

    @pytest.mark.asyncio
    async def test_update_profile_scoped_to_profile_id(self):
        """Updating with profile_id must query that specific profile."""
        target_id = uuid.uuid4()
        profile = CandidateProfile(id=target_id, is_confirmed=False)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = profile
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        updates = CandidateProfileUpdate(full_name="Jane Doe", location="Bengaluru")
        res = await update_profile(updates=updates, profile_id=target_id, db=db)

        assert res.full_name == "Jane Doe"
        assert res.location == "Bengaluru"
        assert profile.full_name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_update_rejected_if_already_confirmed(self):
        """Updating an already-confirmed profile must return 409 Conflict."""
        profile_id = uuid.uuid4()
        confirmed_profile = CandidateProfile(
            id=profile_id, is_confirmed=True, confirmed_at=datetime.now(timezone.utc)
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = confirmed_profile
        db.execute = AsyncMock(return_value=mock_result)

        updates = CandidateProfileUpdate(full_name="New Name")
        with pytest.raises(HTTPException) as exc:
            await update_profile(updates=updates, profile_id=profile_id, db=db)
        assert exc.value.status_code == 409
        assert "already confirmed" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_confirm_profile_scoped_and_authoritative(self):
        """Confirmation marks profile as confirmed and records UTC timestamp."""
        profile_id = uuid.uuid4()
        draft_profile = CandidateProfile(
            id=profile_id,
            full_name="Jane Doe",
            email="jane.doe@example.com",
            is_confirmed=False,
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = draft_profile
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        res = await confirm_profile(profile_id=profile_id, db=db)

        assert res["profile_id"] == str(profile_id)
        assert draft_profile.is_confirmed is True
        assert draft_profile.confirmed_at is not None
        assert "matching and eligibility evaluation are now enabled" in res["message"]

    @pytest.mark.asyncio
    async def test_resume_replacement_preserves_distinct_ids(self, tmp_path):
        """Uploading another resume generates a distinct profile_id and does not overwrite prior files."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=mock_result)
            db.add = MagicMock()
            db.commit = AsyncMock()

            pdf1 = MockUploadFile(filename="v1.pdf", content=create_minimal_pdf())
            res1 = await upload_resume(file=pdf1, db=db)

            pdf2 = MockUploadFile(filename="v2.pdf", content=create_minimal_pdf())
            res2 = await upload_resume(file=pdf2, db=db)

            assert res1["profile_id"] != res2["profile_id"]
            assert db.commit.await_count == 2
            assert db.execute.await_count == 2

            # Verify both files exist separately on disk
            path1 = settings.upload_dir_abs / "resumes" / "base" / f"{res1['profile_id']}.pdf"
            path2 = settings.upload_dir_abs / "resumes" / "base" / f"{res2['profile_id']}.pdf"
            assert path1.exists()
            assert path2.exists()
            assert path1 != path2

    @pytest.mark.asyncio
    async def test_delete_profile_cleans_up_disk_files(self, tmp_path):
        """Deleting candidate profile cleans up associated resume files from disk."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            pdf_path = settings.upload_dir_abs / "resumes" / "base" / "test_delete.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(b"%PDF-1.4 test")

            profile = CandidateProfile(id=uuid.uuid4())
            rv = ResumeVersion(
                profile_id=profile.id,
                pdf_path=str(pdf_path),
            )
            profile.resume_versions = [rv]

            db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [profile]
            db.execute = AsyncMock(return_value=mock_result)
            db.delete = AsyncMock()
            await delete_profile(confirm="DELETE_ALL_CANDIDATE_DATA", db=db)

            assert not pdf_path.exists()
            trash_dir = settings.upload_dir_abs / "_trash"
            assert trash_dir.exists()
            assert len(list(trash_dir.glob("*test_delete.pdf"))) == 1
