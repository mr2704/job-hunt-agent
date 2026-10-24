"""
SQLAlchemy ORM models.

All tables use UUID primary keys. Timestamps are stored as UTC.
Candidate profile is intentionally EMPTY until the user uploads their resume.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.utcnow()


# ─── Company ──────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(String(255))
    area: Mapped[str | None] = mapped_column(String(255))  # office location area
    founded_year: Mapped[int | None] = mapped_column(Integer)
    website: Mapped[str | None] = mapped_column(String(1024))
    logo_url: Mapped[str | None] = mapped_column(String(1024))
    funding_stage: Mapped[str | None] = mapped_column(String(128))
    bsm_url: Mapped[str | None] = mapped_column(String(1024))
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="company", cascade="all, delete-orphan")


# ─── Job ──────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("external_job_id", "ats_platform", name="uq_job_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Basic info
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255))
    level: Mapped[str | None] = mapped_column(String(128))
    employment_type: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(512))
    remote_policy: Mapped[str | None] = mapped_column(String(128))

    # Requirements
    description: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[list[str] | None] = mapped_column(JSONB)
    preferred_skills: Mapped[list[str] | None] = mapped_column(JSONB)
    experience_min_years: Mapped[int | None] = mapped_column(Integer)
    experience_max_years: Mapped[int | None] = mapped_column(Integer)
    degree_required: Mapped[str | None] = mapped_column(String(512))
    graduation_year_min: Mapped[int | None] = mapped_column(Integer)
    graduation_year_max: Mapped[int | None] = mapped_column(Integer)
    min_cgpa: Mapped[float | None] = mapped_column(Float)
    backlogs_allowed: Mapped[bool | None] = mapped_column(Boolean)

    # Compensation
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    salary_period: Mapped[str | None] = mapped_column(String(50))
    stipend: Mapped[str | None] = mapped_column(String(255))

    # Source tracking
    bsm_url: Mapped[str | None] = mapped_column(String(2048))
    original_url: Mapped[str | None] = mapped_column(String(2048))
    application_url: Mapped[str | None] = mapped_column(String(2048))
    ats_platform: Mapped[str | None] = mapped_column(String(128))
    external_job_id: Mapped[str | None] = mapped_column(String(512))

    # Timestamps
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Status
    status: Mapped[str] = mapped_column(String(64), default="discovered", index=True)
    # discovered | open | closed | stale | broken | inaccessible

    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    extraction_notes: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    company: Mapped["Company"] = relationship("Company", back_populates="jobs")
    eligibility_results: Mapped[list["EligibilityResult"]] = relationship("EligibilityResult", back_populates="job")
    match_scores: Mapped[list["MatchScore"]] = relationship("MatchScore", back_populates="job")
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="job")


# ─── Candidate Profile ────────────────────────────────────────────────────────

class CandidateProfile(Base):
    """
    Always starts empty. Only populated through the UI onboarding workflow.
    NEVER pre-populated from conversation context or external sources.
    """
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # All fields nullable — profile starts empty
    full_name: Mapped[str | None] = mapped_column(String(512))
    email: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(String(512))
    linkedin_url: Mapped[str | None] = mapped_column(String(1024))
    github_url: Mapped[str | None] = mapped_column(String(1024))
    portfolio_url: Mapped[str | None] = mapped_column(String(1024))

    # Education
    degree: Mapped[str | None] = mapped_column(String(512))
    major: Mapped[str | None] = mapped_column(String(512))
    institution: Mapped[str | None] = mapped_column(String(512))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    cgpa: Mapped[float | None] = mapped_column(Float)
    cgpa_scale: Mapped[float | None] = mapped_column(Float)  # e.g. 10.0 or 4.0
    percentage: Mapped[float | None] = mapped_column(Float)
    backlogs: Mapped[int | None] = mapped_column(Integer)

    # Experience
    total_experience_months: Mapped[int | None] = mapped_column(Integer)
    skills: Mapped[list[str] | None] = mapped_column(JSONB)  # explicitly stated skills only
    work_experience: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    projects: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    certifications: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    achievements: Mapped[list[str] | None] = mapped_column(JSONB)

    # Preferences (user-provided only)
    preferred_roles: Mapped[list[str] | None] = mapped_column(JSONB)
    preferred_locations: Mapped[list[str] | None] = mapped_column(JSONB)
    open_to_remote: Mapped[bool | None] = mapped_column(Boolean)
    open_to_relocation: Mapped[bool | None] = mapped_column(Boolean)
    expected_salary_min: Mapped[int | None] = mapped_column(Integer)
    expected_salary_max: Mapped[int | None] = mapped_column(Integer)
    notice_period_days: Mapped[int | None] = mapped_column(Integer)
    work_authorization: Mapped[str | None] = mapped_column(String(255))

    # Lifecycle
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    resume_versions: Mapped[list["ResumeVersion"]] = relationship(
        "ResumeVersion", back_populates="profile", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if "is_confirmed" not in kwargs:
            self.is_confirmed = False
        if "version" not in kwargs:
            self.version = 1
        if "created_at" not in kwargs:
            self.created_at = _now()
        if "updated_at" not in kwargs:
            self.updated_at = _now()



# ─── Resume Version ───────────────────────────────────────────────────────────

class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    label: Mapped[str | None] = mapped_column(String(255))  # "base", "tailored_<job_id>"

    # File paths (relative to upload_dir)
    pdf_path: Mapped[str | None] = mapped_column(String(2048))
    tex_path: Mapped[str | None] = mapped_column(String(2048))
    latex_zip_path: Mapped[str | None] = mapped_column(String(2048))

    is_base: Mapped[bool] = mapped_column(Boolean, default=False)
    is_tailored: Mapped[bool] = mapped_column(Boolean, default=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    profile: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="resume_versions")


# ─── Eligibility Result ───────────────────────────────────────────────────────

class EligibilityResult(Base):
    __tablename__ = "eligibility_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Statuses: eligible | potentially_eligible | ineligible | needs_manual_verification
    overall_status: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    # Each check: {requirement, job_evidence, profile_evidence, decision, explanation, missing_info}

    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    methodology_version: Mapped[str] = mapped_column(String(64), default="v1")

    job: Mapped["Job"] = relationship("Job", back_populates="eligibility_results")


# ─── Match Score ──────────────────────────────────────────────────────────────

class MatchScore(Base):
    __tablename__ = "match_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)

    total_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100

    # Score breakdown (configurable weights)
    required_skills_score: Mapped[float | None] = mapped_column(Float)
    projects_score: Mapped[float | None] = mapped_column(Float)
    role_alignment_score: Mapped[float | None] = mapped_column(Float)
    education_score: Mapped[float | None] = mapped_column(Float)
    preferred_skills_score: Mapped[float | None] = mapped_column(Float)

    matching_skills: Mapped[list[str] | None] = mapped_column(JSONB)
    missing_mandatory_skills: Mapped[list[str] | None] = mapped_column(JSONB)
    missing_preferred_skills: Mapped[list[str] | None] = mapped_column(JSONB)
    relevant_projects: Mapped[list[str] | None] = mapped_column(JSONB)
    evidence: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    suggested_changes: Mapped[list[str] | None] = mapped_column(JSONB)
    tailoring_worthwhile: Mapped[bool | None] = mapped_column(Boolean)

    scored_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    methodology_version: Mapped[str] = mapped_column(String(64), default="v1")
    weights_used: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    job: Mapped["Job"] = relationship("Job", back_populates="match_scores")


# ─── Application ──────────────────────────────────────────────────────────────

class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "profile_id", name="uq_application_job_profile"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)

    # Status lifecycle
    status: Mapped[str] = mapped_column(String(64), default="discovered", index=True)
    # discovered → analyzed → eligible → ready_for_review → approved → applied
    # → assessment → interview → offer / rejected / withdrawn
    # Also: ineligible | skipped | expired | needs_manual_action | submission_failed

    # Document paths
    tailored_resume_path: Mapped[str | None] = mapped_column(String(2048))
    cover_letter_path: Mapped[str | None] = mapped_column(String(2048))
    base_resume_version: Mapped[int | None] = mapped_column(Integer)
    profile_version: Mapped[int | None] = mapped_column(Integer)

    # Submission
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    application_reference: Mapped[str | None] = mapped_column(String(512))
    submission_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    submission_screenshot_path: Mapped[str | None] = mapped_column(String(2048))

    # Outcome tracking
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime)
    interview_date: Mapped[datetime | None] = mapped_column(DateTime)
    outcome: Mapped[str | None] = mapped_column(String(64))
    outcome_date: Mapped[datetime | None] = mapped_column(DateTime)

    notes: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    job: Mapped["Job"] = relationship("Job", back_populates="applications")


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(128))
    entity_id: Mapped[str | None] = mapped_column(String(256))
    actor: Mapped[str] = mapped_column(String(128), default="system")
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
