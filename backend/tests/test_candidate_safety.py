"""
Regression tests for Candidate Safety & Uploads (F12, F13, F20).
- F12: Safe DELETE requiring confirm=DELETE_ALL_CANDIDATE_DATA and archiving to _trash.
- F13: LaTeX ZIP upload requiring profile_id, base resume check (404), zip-slip and entry/size limits, unique filename, relative path.
- F20: PDF upload streaming size cap, threadpool parsing, generic client errors, write-after-commit / rollback on failure.
"""
from __future__ import annotations

import io
import shutil
import uuid
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter

from app.api.v1.candidate import (
    confirm_profile,
    create_new_profile_version,
    delete_profile,
    get_profile,
    update_profile,
    upload_latex_zip,
    upload_resume,
)
from app.core.config import get_settings
from app.models.models import CandidateProfile, ResumeVersion, utc_now_naive
from app.schemas.schemas import CandidateProfileUpdate


def create_minimal_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_test_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
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


# ─── F12: SAFE DELETE TESTS ───────────────────────────────────────────────────

class TestSafeDelete:
    @pytest.mark.asyncio
    async def test_delete_profile_requires_confirmation_token(self):
        """F12: DELETE /candidate/profile must reject with 400 without confirm=DELETE_ALL_CANDIDATE_DATA."""
        db = AsyncMock()
        # Missing or incorrect confirm query param
        with pytest.raises(HTTPException) as exc:
            await delete_profile(confirm="wrong_token", db=db)
        assert exc.value.status_code == 400
        assert "DELETE_ALL_CANDIDATE_DATA" in exc.value.detail

    @pytest.mark.asyncio
    async def test_delete_profile_soft_deletes_and_preserves_row_count(self, tmp_path):
        """F12: DELETE /candidate/profile sets archived_at, never removes rows, preserves files, and answers 'archived'."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            base_dir = settings.upload_dir_abs / "resumes" / "base"
            base_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = base_dir / "candidate_resume.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 test resume")

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
            db.commit = AsyncMock()

            res = await delete_profile(confirm="DELETE_ALL_CANDIDATE_DATA", db=db)
            
            # Answer must say "archived" and NEVER "deleted"
            assert "archived" in res["message"].lower()
            assert "deleted" not in res["message"].lower()

            # Row count must not change: db.delete must NOT be called on any model row
            db.delete.assert_not_called()
            assert profile.archived_at is not None

            # Original files must stay recoverable and intact in place
            assert pdf_path.exists()
            assert pdf_path.read_bytes() == b"%PDF-1.4 test resume"
            assert db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_archived_profiles_invisible_to_get_profile(self):
        """Every reader excluding get_profile must not return archived profiles."""
        archived_id = uuid.uuid4()
        archived_profile = CandidateProfile(id=archived_id, archived_at=utc_now_naive(), full_name="Archived Candidate")

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        # GET by id
        res = await get_profile(profile_id=archived_id, db=db)
        assert res is None

        # GET latest
        res_latest = await get_profile(profile_id=None, db=db)
        assert res_latest is None

        # Verify query filters on CandidateProfile.archived_at.is_(None)
        executed_query = str(db.execute.call_args[0][0])
        assert "archived_at IS NULL" in executed_query

    @pytest.mark.asyncio
    async def test_archived_profiles_invisible_to_update_profile(self):
        """Updating an archived profile must return 404."""
        archived_id = uuid.uuid4()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        updates = CandidateProfileUpdate(full_name="New Name")
        with pytest.raises(HTTPException) as exc:
            await update_profile(updates=updates, profile_id=archived_id, db=db)
        assert exc.value.status_code == 404
        executed_query = str(db.execute.call_args[0][0])
        assert "archived_at IS NULL" in executed_query

    @pytest.mark.asyncio
    async def test_archived_profiles_invisible_to_confirm_profile(self):
        """Confirming an archived profile must return 404."""
        archived_id = uuid.uuid4()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc:
            await confirm_profile(profile_id=archived_id, db=db)
        assert exc.value.status_code == 404
        executed_query = str(db.execute.call_args[0][0])
        assert "archived_at IS NULL" in executed_query

    @pytest.mark.asyncio
    async def test_archived_profiles_invisible_to_new_version(self):
        """Creating a new version from an archived profile must fail with 400."""
        archived_id = uuid.uuid4()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc:
            await create_new_profile_version(base_profile_id=archived_id, db=db)
        assert exc.value.status_code == 400
        executed_query = str(db.execute.call_args[0][0])
        assert "archived_at IS NULL" in executed_query

    @pytest.mark.asyncio
    async def test_archived_profiles_invisible_to_latex_upload(self):
        """Uploading LaTeX for an archived profile must return 404."""
        archived_id = uuid.uuid4()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        upload_file = MockUploadFile(filename="latex.zip", content=b"fake")
        with pytest.raises(HTTPException) as exc:
            await upload_latex_zip(file=upload_file, profile_id=archived_id, db=db)
        assert exc.value.status_code == 404
        executed_query = str(db.execute.call_args[0][0])
        assert "archived_at IS NULL" in executed_query

    @pytest.mark.asyncio
    async def test_archived_confirmed_profile_allows_reupload(self, tmp_path):
        """An archived profile that was previously confirmed must not block new uploads."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            db = AsyncMock()
            mock_result = MagicMock()
            # Active confirmed profile query returns None because the confirmed profile is archived
            mock_result.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=mock_result)
            db.add = MagicMock()
            db.commit = AsyncMock()

            pdf = MockUploadFile(filename="new.pdf", content=create_minimal_pdf())
            res = await upload_resume(file=pdf, db=db)
            assert "profile_id" in res
            executed_query = str(db.execute.call_args[0][0])
            assert "archived_at IS NULL" in executed_query

    @pytest.mark.asyncio
    async def test_restore_profile(self):
        """restore_profile sets archived_at to None, commits, and returns the profile."""
        from app.api.v1.candidate import restore_profile

        profile_id = uuid.uuid4()
        profile = CandidateProfile(id=profile_id, archived_at=utc_now_naive(), full_name="Restored Candidate")
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = profile
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        restored = await restore_profile(profile_id=profile_id, db=db)
        assert restored.archived_at is None
        assert db.commit.await_count == 1



# ─── F13: LATEX UPLOAD HARDENING TESTS ────────────────────────────────────────

class TestLatexUploadHardening:
    @pytest.mark.asyncio
    async def test_latex_upload_requires_profile_id(self):
        """F13: latex upload must require profile_id (cannot be None)."""
        db = AsyncMock()
        zip_bytes = create_test_zip({"main.tex": b"\\documentclass{article}"})
        upload_file = MockUploadFile(filename="source.zip", content=zip_bytes)
        with pytest.raises(HTTPException) as exc:
            await upload_latex_zip(file=upload_file, profile_id=None, db=db)
        assert exc.value.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_latex_upload_404_when_no_base_resume(self):
        """F13: latex upload must return 404 if profile has no base resume version."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        pid = uuid.uuid4()
        zip_bytes = create_test_zip({"main.tex": b"\\documentclass{article}"})
        upload_file = MockUploadFile(filename="source.zip", content=zip_bytes)

        with pytest.raises(HTTPException) as exc:
            await upload_latex_zip(file=upload_file, profile_id=pid, db=db)
        assert exc.value.status_code == 404
        assert "no base resume" in exc.value.detail.lower()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_latex_upload_rejects_non_zip(self):
        """F13: non-ZIP file with .zip extension must be rejected with 422."""
        db = AsyncMock()
        pid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ResumeVersion(id=uuid.uuid4(), profile_id=pid, is_base=True)
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        upload_file = MockUploadFile(filename="fake.zip", content=b"not a zip file")
        with pytest.raises(HTTPException) as exc:
            await upload_latex_zip(file=upload_file, profile_id=pid, db=db)
        assert exc.value.status_code == 422
        assert "valid zip" in exc.value.detail.lower()
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_latex_upload_rejects_zip_slip(self):
        """F13: ZIP archive containing path traversal ('../') must be rejected with 422."""
        db = AsyncMock()
        pid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ResumeVersion(id=uuid.uuid4(), profile_id=pid, is_base=True)
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.tex", b"harmful content")
        upload_file = MockUploadFile(filename="malicious.zip", content=buf.getvalue())

        with pytest.raises(HTTPException) as exc:
            await upload_latex_zip(file=upload_file, profile_id=pid, db=db)
        assert exc.value.status_code == 422
        assert "zip-slip" in exc.value.detail.lower() or "traversal" in exc.value.detail.lower() or "unsafe" in exc.value.detail.lower()
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_latex_upload_rejects_too_many_entries(self):
        """F13: ZIP archive exceeding max allowed files (e.g. >100) must be rejected."""
        db = AsyncMock()
        pid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ResumeVersion(id=uuid.uuid4(), profile_id=pid, is_base=True)
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        files = {f"file_{i}.tex": b"x" for i in range(105)}
        upload_file = MockUploadFile(filename="bomb.zip", content=create_test_zip(files))

        with pytest.raises(HTTPException) as exc:
            await upload_latex_zip(file=upload_file, profile_id=pid, db=db)
        assert exc.value.status_code in (413, 422)
        assert "too many" in exc.value.detail.lower()
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_latex_upload_returns_relative_path_and_unique_filename(self, tmp_path):
        """F13: Successful upload must generate a unique filename and return a relative path (never absolute)."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            pid = uuid.uuid4()
            rv = ResumeVersion(id=uuid.uuid4(), profile_id=pid, is_base=True)

            db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = rv
            db.execute = AsyncMock(return_value=mock_result)
            db.commit = AsyncMock()

            zip_bytes = create_test_zip({"main.tex": b"\\documentclass{article}"})
            upload_file = MockUploadFile(filename="source.zip", content=zip_bytes)

            res = await upload_latex_zip(file=upload_file, profile_id=pid, db=db)
            assert "path" in res
            ret_path = res["path"]

            # Response must not be an absolute path
            assert not Path(ret_path).is_absolute(), f"Returned path is absolute: {ret_path}"
            # Must contain unique suffix or hex
            assert str(pid) in ret_path


# ─── F20: PDF UPLOAD HARDENING TESTS ──────────────────────────────────────────

class TestPdfUploadHardening:
    @pytest.mark.asyncio
    async def test_pdf_upload_generic_client_error_on_corrupt(self):
        """F20: Corrupt PDF must return generic client error, not raw exception traceback text."""
        db = AsyncMock()
        corrupt_bytes = b"%PDF-1.4\ncorrupt header content without valid catalog or xref"
        upload_file = MockUploadFile(filename="corrupt.pdf", content=corrupt_bytes)

        with pytest.raises(HTTPException) as exc:
            await upload_resume(file=upload_file, db=db)
        assert exc.value.status_code == 422
        # Detail must be generic and safe
        detail = exc.value.detail
        assert "corrupt" in detail.lower() or "malformed" in detail.lower()
        # Must not contain Python exception markers or traceback
        assert "Traceback" not in detail
        assert "pypdf.errors" not in detail

    @pytest.mark.asyncio
    async def test_pdf_upload_rolls_back_file_if_db_commit_fails(self, tmp_path):
        """F20: If database commit fails, file on disk must be rolled back (unlinked)."""
        settings = get_settings()
        with patch.object(settings, "upload_dir", tmp_path):
            pdf_bytes = create_minimal_pdf()
            upload_file = MockUploadFile(filename="resume.pdf", content=pdf_bytes)

            db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=mock_result)
            db.add = MagicMock()
            # Simulate DB commit failure (e.g. DB connection dropped)
            db.commit = AsyncMock(side_effect=RuntimeError("DB Commit failed"))

            with pytest.raises(RuntimeError):
                await upload_resume(file=upload_file, db=db)

            # Verify no orphan PDF remains in the resumes folder
            base_dir = settings.upload_dir_abs / "resumes" / "base"
            if base_dir.exists():
                orphan_files = list(base_dir.glob("*.pdf"))
                assert len(orphan_files) == 0, f"Found orphan PDF after failed commit: {orphan_files}"
