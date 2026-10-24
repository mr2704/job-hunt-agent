"""
Candidate profile API — upload resume, manage profile, confirm.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import CandidateProfile, ResumeVersion, utc_now_naive
from app.schemas.schemas import CandidateProfileOut, CandidateProfileUpdate
from app.services.candidate.resume_parser import ResumeParser

router = APIRouter(prefix="/candidate", tags=["candidate"])
settings = get_settings()

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


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

    contents = await file.read()
    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty. Please upload a valid PDF resume.",
        )

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
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
        from pypdf.errors import PdfReadError

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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The uploaded PDF file is corrupt or malformed: {str(exc)}",
        )

    # Save to disk
    upload_dir = settings.upload_dir_abs / "resumes" / "base"
    upload_dir.mkdir(parents=True, exist_ok=True)
    profile_id = uuid.uuid4()
    save_path = upload_dir / f"{profile_id}.pdf"
    save_path.write_bytes(contents)

    # Parse
    parser = ResumeParser()
    extracted = await parser.parse_pdf(io.BytesIO(contents))

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

    try:
        rel_pdf_path = str(save_path.relative_to(settings.base_dir))
    except ValueError:
        rel_pdf_path = str(save_path)

    resume_version = ResumeVersion(
        profile_id=profile_id,
        version=1,
        label="base",
        pdf_path=rel_pdf_path,
        is_base=True,
        is_tailored=False,
    )
    db.add(resume_version)
    await db.commit()

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
    profile_id: uuid.UUID = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload the original Overleaf/LaTeX source ZIP for the base resume."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=422,
            detail="Only ZIP files are accepted for LaTeX source upload.",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large.")

    # Save
    upload_dir = settings.upload_dir_abs / "resumes" / "base"
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / f"{profile_id or 'base'}_latex.zip"
    save_path.write_bytes(contents)

    # Update resume version record
    if profile_id:
        result = await db.execute(
            select(ResumeVersion).where(
                ResumeVersion.profile_id == profile_id,
                ResumeVersion.is_base.is_(True),
            )
        )
        rv = result.scalar_one_or_none()
        if rv:
            rv.latex_zip_path = str(save_path.relative_to(settings.base_dir))
            await db.commit()

    return {
        "message": "LaTeX source uploaded. This will be used as the template for resume tailoring.",
        "path": str(save_path),
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
async def delete_profile(db: AsyncSession = Depends(get_db)) -> dict:
    """Delete all candidate profile data and uploaded resumes."""
    result = await db.execute(
        select(CandidateProfile).options(selectinload(CandidateProfile.resume_versions))
    )
    profiles = result.scalars().all()
    for p in profiles:
        for rv in p.resume_versions:
            if rv.pdf_path:
                p_path = Path(rv.pdf_path)
                if not p_path.is_absolute():
                    p_path = settings.base_dir / p_path
                if p_path.is_file():
                    try:
                        p_path.unlink()
                    except OSError:
                        pass
            if rv.latex_zip_path:
                z_path = Path(rv.latex_zip_path)
                if not z_path.is_absolute():
                    z_path = settings.base_dir / z_path
                if z_path.is_file():
                    try:
                        z_path.unlink()
                    except OSError:
                        pass
        await db.delete(p)
    await db.commit()
    return {"message": "All candidate data deleted."}

