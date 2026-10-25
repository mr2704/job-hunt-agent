"""
Candidate profile API — upload resume, manage profile, confirm.
"""
from __future__ import annotations

import io
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import CandidateProfile, ResumeVersion, utc_now_naive
from app.schemas.schemas import CandidateProfileOut, CandidateProfileUpdate
from app.services.candidate.resume_parser import ResumeParser

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/candidate", tags=["candidate"])
settings = get_settings()

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024
MAX_ZIP_ENTRIES = 100
MAX_ZIP_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB
DELETE_CONFIRMATION_TOKEN = "DELETE_ALL_CANDIDATE_DATA"


@router.get("/profile", response_model=CandidateProfileOut | None)
async def get_profile(
    profile_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileOut | None:
    """Return the candidate profile by id or latest, or null if not yet created."""
    if profile_id:
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == profile_id)
        )
    else:
        result = await db.execute(
            select(CandidateProfile).order_by(CandidateProfile.created_at.desc()).limit(1)
        )
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    return CandidateProfileOut.model_validate(profile)


@router.post("/resume/upload")
async def upload_resume(
    file: UploadFile = File(..., description="Base resume PDF"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload the candidate's base resume (PDF).
    Parses the PDF to extract candidate information.
    Returns extracted fields for review — nothing is confirmed yet.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted for resume upload.",
        )

    # Stream with size cap to prevent memory exhaustion (F20)
    chunks = []
    total_size = 0
    chunk_size = 64 * 1024
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
                )
            chunks.append(chunk)
        contents = b"".join(chunks)
    except TypeError:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
            )

    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty. Please upload a valid PDF resume.",
        )

    # Server-side verification of file magic bytes and content integrity
    header_preview = contents[:1024].lstrip(b"\xef\xbb\xbf")
    if not header_preview.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file is not a valid PDF document.",
        )

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contents))
        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password-protected PDFs are not supported. Please upload an unencrypted PDF.",
            )
        if len(reader.pages) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The uploaded PDF contains no pages.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        # F20: Generic client error, no raw exception string leakage
        logger.warning("pdf_validation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded PDF file is corrupt or malformed, and could not be parsed.",
        )

    # CPU-intensive PDF parsing in a threadpool (F20)
    parser = ResumeParser()
    extracted = await parser.parse_pdf(io.BytesIO(contents))

    profile_id = uuid.uuid4()
    upload_dir = settings.upload_dir_abs / "resumes" / "base"
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / f"{profile_id}.pdf"

    try:
        rel_pdf_path = str(save_path.relative_to(settings.base_dir))
    except ValueError:
        rel_pdf_path = f"candidate_data/resumes/base/{profile_id}.pdf"

    # Create empty profile (not yet confirmed)
    profile = CandidateProfile(
        id=profile_id,
        version=1,
        is_confirmed=False,
        **{
            k: v
            for k, v in extracted.items()
            if hasattr(CandidateProfile, k) and v is not None and not k.startswith("_")
        },
    )
    db.add(profile)

    resume_version = ResumeVersion(
        profile_id=profile_id,
        version=1,
        label="base",
        pdf_path=rel_pdf_path,
        is_base=True,
        is_tailored=False,
    )
    db.add(resume_version)

    # F20: Commit DB first, write file, and unlink on failure
    try:
        await db.commit()
        save_path.write_bytes(contents)
    except Exception:
        if save_path.exists():
            try:
                save_path.unlink()
            except OSError:
                pass
        raise

    return {
        "message": "Resume uploaded successfully. Please review the extracted information below and confirm your profile.",
        "profile_id": str(profile_id),
        "extracted": extracted,
        "warnings": extracted.get("_warnings", []),
        "next_step": "Review the extracted profile at GET /api/v1/candidate/profile, then PATCH to correct errors, then POST /api/v1/candidate/profile/confirm",
    }


@router.post("/latex/upload")
async def upload_latex_zip(
    file: UploadFile = File(..., description="LaTeX source ZIP"),
    profile_id: uuid.UUID = Query(..., description="Candidate profile ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload the original Overleaf/LaTeX source ZIP for the base resume."""
    if not profile_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="profile_id query parameter is required.",
        )

    # Verify base resume exists for this profile_id (F13)
    result = await db.execute(
        select(ResumeVersion).where(
            ResumeVersion.profile_id == profile_id,
            ResumeVersion.is_base.is_(True),
        )
    )
    rv = result.scalar_one_or_none()
    if not rv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No base resume found for candidate profile {profile_id}. Please upload a base resume first.",
        )

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only ZIP files are accepted for LaTeX source upload.",
        )

    # Stream with size cap (F13)
    chunks = []
    total_size = 0
    chunk_size = 64 * 1024
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
                )
            chunks.append(chunk)
        contents = b"".join(chunks)
    except TypeError:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
            )

    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty. Please upload a valid LaTeX source ZIP archive.",
        )

    # Validate ZIP integrity (F13)
    if not zipfile.is_zipfile(io.BytesIO(contents)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file is not a valid ZIP archive.",
        )

    try:
        with zipfile.ZipFile(io.BytesIO(contents), "r") as zf:
            infolist = zf.infolist()
            if len(infolist) > MAX_ZIP_ENTRIES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"ZIP archive contains too many files ({len(infolist)}). Maximum allowed is {MAX_ZIP_ENTRIES}.",
                )
            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uncompressed ZIP content exceeds maximum size of 50 MB.",
                )
            for info in infolist:
                # Zip-Slip defense
                fname = info.filename
                if fname.startswith("/") or fname.startswith("\\") or Path(fname).is_absolute() or ".." in Path(fname).parts:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="ZIP archive contains unsafe member path (Zip-Slip detected).",
                    )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("zip_validation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded ZIP archive is corrupt or could not be read.",
        )

    # Save to unique filename (F13)
    unique_suffix = uuid.uuid4().hex[:8]
    upload_dir = settings.upload_dir_abs / "resumes" / "base"
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / f"{profile_id}_{unique_suffix}_latex.zip"

    try:
        rel_path = str(save_path.relative_to(settings.base_dir))
    except ValueError:
        rel_path = f"candidate_data/resumes/base/{save_path.name}"

    rv.latex_zip_path = rel_path

    # Commit DB first, write file, and rollback on failure (F13)
    try:
        await db.commit()
        save_path.write_bytes(contents)
    except Exception:
        if save_path.exists():
            try:
                save_path.unlink()
            except OSError:
                pass
        raise

    return {
        "message": "LaTeX source uploaded. This will be used as the template for resume tailoring.",
        "path": rel_path,
    }


@router.patch("/profile", response_model=CandidateProfileOut)
async def update_profile(
    updates: CandidateProfileUpdate,
    profile_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileOut:
    """Update editable fields in the candidate profile before confirmation."""
    if profile_id:
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == profile_id)
        )
    else:
        result = await db.execute(
            select(CandidateProfile).order_by(CandidateProfile.created_at.desc()).limit(1)
        )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")

    if profile.is_confirmed:
        raise HTTPException(
            status_code=409,
            detail="Profile is already confirmed. To make changes, create a new version.",
        )

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    return CandidateProfileOut.model_validate(profile)


@router.post("/profile/confirm")
async def confirm_profile(
    profile_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Confirm the candidate profile. This enables personalized matching and eligibility evaluation.
    Cannot be undone — start a new profile version to make further changes.
    """
    from datetime import datetime, timezone

    if profile_id:
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == profile_id)
        )
    else:
        result = await db.execute(
            select(CandidateProfile).order_by(CandidateProfile.created_at.desc()).limit(1)
        )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found.")

    if profile.is_confirmed:
        return {
            "message": "Profile was already confirmed.",
            "profile_id": str(profile.id),
            "version": profile.version,
        }

    profile.is_confirmed = True
    profile.confirmed_at = utc_now_naive()
    await db.commit()

    return {
        "message": "Profile confirmed. Personalized matching and eligibility evaluation are now enabled.",
        "profile_id": str(profile.id),
        "version": profile.version,
    }


@router.delete("/profile")
async def delete_profile(
    confirm: str = Query(..., description="Confirmation token required to delete all candidate data"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Safely delete all candidate profile records from database and archive
    uploaded resume files to candidate_data/_trash. Never hard-deletes files.
    """
    if confirm != DELETE_CONFIRMATION_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Confirmation token '{DELETE_CONFIRMATION_TOKEN}' required to delete candidate data.",
        )

    result = await db.execute(
        select(CandidateProfile).options(selectinload(CandidateProfile.resume_versions))
    )
    profiles = result.scalars().all()
    if not profiles:
        return {"message": "No candidate profiles found to delete.", "archived_count": 0}

    # Collect files to archive
    files_to_archive: list[Path] = []
    for p in profiles:
        for rv in p.resume_versions:
            if rv.pdf_path:
                p_path = Path(rv.pdf_path)
                if not p_path.is_absolute():
                    p_path = settings.base_dir / p_path
                if p_path.is_file():
                    files_to_archive.append(p_path)
            if rv.latex_zip_path:
                z_path = Path(rv.latex_zip_path)
                if not z_path.is_absolute():
                    z_path = settings.base_dir / z_path
                if z_path.is_file():
                    files_to_archive.append(z_path)
        await db.delete(p)

    # Commit DB deletion first
    await db.commit()

    # Move files to _trash only AFTER DB commit succeeds (never hard-delete)
    trash_dir = settings.upload_dir_abs / "_trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    archived_count = 0
    timestamp = utc_now_naive().strftime("%Y%m%d_%H%M%S")

    for file_path in files_to_archive:
        if file_path.is_file():
            unique_name = f"{timestamp}_{uuid.uuid4().hex[:6]}_{file_path.name}"
            dest = trash_dir / unique_name
            try:
                shutil.move(str(file_path), str(dest))
                archived_count += 1
            except OSError as err:
                logger.warning("archive_file_failed", file=str(file_path), error=str(err))

    return {
        "message": f"All candidate data deleted. {archived_count} files safely archived to _trash.",
        "archived_count": archived_count,
    }

