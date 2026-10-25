"""
Regression tests for Profile Versioning & Confirmation (F17, F18, F19).
- F17: Re-upload must not silently replace a confirmed profile (returns 409).
- F18: POST /candidate/profile/new-version clones confirmed profile with incremented version and unconfirmed status.
- F19: POST /candidate/profile/confirm requires profile_id (no race with latest) and enforces required fields (full_name, email).
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter

from app.api.v1.candidate import (
    confirm_profile,
    create_new_profile_version,
    upload_resume,
)
from app.core.config import get_settings
from app.models.models import CandidateProfile, ResumeVersion


def create_minimal_pdf() -> bytes:
    writer = PdfWriter()
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


class TestProfileVersioningAndConfirm:
    """Regression tests for F17, F18, F19."""

    @pytest.mark.asyncio
    async def test_reupload_rejected_if_active_profile_confirmed(self, tmp_path):
        """F17: Uploading a new resume when an active confirmed profile exists returns 409 Conflict."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            confirmed_profile = CandidateProfile(
                id=uuid.uuid4(),
                full_name="Confirmed Candidate",
                email="candidate@example.com",
                is_confirmed=True,
                version=1,
            )

            db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = confirmed_profile
            db.execute = AsyncMock(return_value=mock_result)

            upload_file = MockUploadFile(filename="new_resume.pdf", content=create_minimal_pdf())
            with pytest.raises(HTTPException) as exc:
                await upload_resume(file=upload_file, db=db)

            assert exc.value.status_code == 409
            assert "confirmed" in exc.value.detail.lower()
            assert "new-version" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_new_version_clones_confirmed_profile(self):
        """F18: create_new_profile_version increments version, resets confirmation, and clones fields."""
        old_id = uuid.uuid4()
        confirmed_profile = CandidateProfile(
            id=old_id,
            full_name="Jane Doe",
            email="jane@example.com",
            location="Bengaluru",
            skills=["Python", "FastAPI"],
            is_confirmed=True,
            confirmed_at=datetime.now(timezone.utc),
            version=1,
        )
        base_rv = ResumeVersion(
            id=uuid.uuid4(),
            profile_id=old_id,
            version=1,
            pdf_path="resumes/base/resume.pdf",
            is_base=True,
        )
        confirmed_profile.resume_versions = [base_rv]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = confirmed_profile
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.commit = AsyncMock()

        new_profile_out = await create_new_profile_version(base_profile_id=old_id, db=db)

        assert new_profile_out.version == 2
        assert new_profile_out.is_confirmed is False
        assert new_profile_out.full_name == "Jane Doe"
        assert new_profile_out.email == "jane@example.com"
        assert new_profile_out.skills == ["Python", "FastAPI"]
        assert new_profile_out.id != old_id

        # Verify new CandidateProfile was added to DB
        added_objects = [call[0][0] for call in db.add.call_args_list]
        new_profiles = [o for o in added_objects if isinstance(o, CandidateProfile)]
        assert len(new_profiles) == 1
        assert new_profiles[0].version == 2
        assert new_profiles[0].is_confirmed is False

    @pytest.mark.asyncio
    async def test_create_new_version_fails_if_no_confirmed_profile(self):
        """F18: create_new_profile_version fails with 400 if no confirmed profile exists."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc:
            await create_new_profile_version(base_profile_id=uuid.uuid4(), db=db)
        assert exc.value.status_code in (400, 404)
        assert "no confirmed profile" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_confirm_requires_profile_id(self):
        """F19: confirm_profile must require profile_id (cannot be None to prevent race condition)."""
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await confirm_profile(profile_id=None, db=db)
        assert exc.value.status_code in (400, 422)
        assert "profile_id" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_confirm_requires_full_name_and_email(self):
        """F19: confirm_profile must reject with 422 if required fields (full_name, email) are missing."""
        pid = uuid.uuid4()
        incomplete_profile = CandidateProfile(
            id=pid,
            full_name=None,  # Missing full name
            email="candidate@example.com",
            is_confirmed=False,
            version=1,
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = incomplete_profile
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc:
            await confirm_profile(profile_id=pid, db=db)
        assert exc.value.status_code == 422
        assert "full_name" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_confirm_succeeds_when_required_fields_present(self):
        """F19: confirm_profile succeeds and marks confirmed when required fields are present."""
        pid = uuid.uuid4()
        valid_profile = CandidateProfile(
            id=pid,
            full_name="Jane Doe",
            email="jane@example.com",
            is_confirmed=False,
            version=1,
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = valid_profile
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        res = await confirm_profile(profile_id=pid, db=db)
        assert res["profile_id"] == str(pid)
        assert valid_profile.is_confirmed is True
        assert valid_profile.confirmed_at is not None
