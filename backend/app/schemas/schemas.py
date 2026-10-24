"""
Pydantic response/request schemas for the REST API.
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Common ────────────────────────────────────────────────────────────────────

class PagedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]


# ── Company schemas ───────────────────────────────────────────────────────────

class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    sector: str | None
    area: str | None
    founded_year: int | None
    website: str | None
    logo_url: str | None
    funding_stage: str | None
    bsm_url: str | None
    is_active: bool
    discovered_at: datetime
    last_verified_at: datetime | None


# ── Job schemas ───────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    department: str | None
    level: str | None
    employment_type: str | None
    location: str | None
    remote_policy: str | None
    description: str | None
    required_skills: list[str] | None
    preferred_skills: list[str] | None
    experience_min_years: int | None
    experience_max_years: int | None
    degree_required: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    bsm_url: str | None
    original_url: str | None
    application_url: str | None
    ats_platform: str | None
    posted_at: datetime | None
    discovered_at: datetime
    last_verified_at: datetime | None
    status: str
    extraction_confidence: float | None


class JobWithCompanyOut(JobOut):
    company: CompanyOut | None = None


# ── Candidate profile schemas ─────────────────────────────────────────────────

class CandidateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    full_name: str | None
    email: str | None
    phone: str | None
    location: str | None
    linkedin_url: str | None
    github_url: str | None
    degree: str | None
    major: str | None
    institution: str | None
    graduation_year: int | None
    cgpa: float | None
    cgpa_scale: float | None
    percentage: float | None
    backlogs: int | None
    total_experience_months: int | None
    skills: list[str] | None
    work_experience: list[dict[str, Any]] | None
    projects: list[dict[str, Any]] | None
    certifications: list[dict[str, Any]] | None
    achievements: list[str] | None
    preferred_roles: list[str] | None
    preferred_locations: list[str] | None
    open_to_remote: bool | None
    open_to_relocation: bool | None
    expected_salary_min: int | None
    expected_salary_max: int | None
    notice_period_days: int | None
    work_authorization: str | None
    is_confirmed: bool
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CandidateProfileUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    degree: str | None = None
    major: str | None = None
    institution: str | None = None
    graduation_year: int | None = None
    cgpa: float | None = None
    cgpa_scale: float | None = None
    percentage: float | None = None
    backlogs: int | None = None
    total_experience_months: int | None = None
    skills: list[str] | None = None
    work_experience: list[dict[str, Any]] | None = None
    projects: list[dict[str, Any]] | None = None
    certifications: list[dict[str, Any]] | None = None
    achievements: list[str] | None = None
    preferred_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    open_to_remote: bool | None = None
    open_to_relocation: bool | None = None
    expected_salary_min: int | None = None
    expected_salary_max: int | None = None
    notice_period_days: int | None = None
    work_authorization: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                raise ValueError("Invalid email format")
        return v

    @field_validator("graduation_year")
    @classmethod
    def validate_graduation_year(cls, v: int | None) -> int | None:
        if v is not None:
            if v < 1970 or v > 2035:
                raise ValueError("Graduation year must be a valid 4-digit year between 1970 and 2035")
        return v

    @field_validator("cgpa")
    @classmethod
    def validate_cgpa(cls, v: float | None) -> float | None:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or v < 0:
                raise ValueError("CGPA must be a non-negative finite number")
        return v

    @field_validator("cgpa_scale")
    @classmethod
    def validate_cgpa_scale(cls, v: float | None) -> float | None:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or v <= 0:
                raise ValueError("CGPA scale must be a positive finite number")
        return v

    @model_validator(mode="after")
    def validate_cgpa_against_scale(self) -> CandidateProfileUpdate:
        if self.cgpa is not None and self.cgpa_scale is not None:
            if self.cgpa > self.cgpa_scale:
                raise ValueError(f"CGPA ({self.cgpa}) cannot exceed stated CGPA scale ({self.cgpa_scale})")
        return self

    @field_validator("skills")
    @classmethod
    def validate_and_normalize_skills(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            seen: set[str] = set()
            normalized: list[str] = []
            for item in v:
                cleaned = item.strip()
                if cleaned and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    normalized.append(cleaned)
            return normalized
        return v


# ── Eligibility schemas ───────────────────────────────────────────────────────

class EligibilityCheck(BaseModel):
    requirement: str
    job_evidence: str | None
    profile_evidence: str | None
    decision: str  # pass | fail | unknown | not_applicable
    explanation: str
    missing_info: str | None
    is_mandatory: bool


class EligibilityResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    profile_id: uuid.UUID
    profile_version: int
    overall_status: str
    checks: list[dict[str, Any]]
    evaluated_at: datetime
    methodology_version: str


# ── Match score schemas ───────────────────────────────────────────────────────

class MatchScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    profile_id: uuid.UUID
    profile_version: int
    total_score: float
    required_skills_score: float | None
    projects_score: float | None
    role_alignment_score: float | None
    education_score: float | None
    preferred_skills_score: float | None
    matching_skills: list[str] | None
    missing_mandatory_skills: list[str] | None
    missing_preferred_skills: list[str] | None
    relevant_projects: list[str] | None
    evidence: list[dict[str, Any]] | None
    suggested_changes: list[str] | None
    tailoring_worthwhile: bool | None
    scored_at: datetime
    methodology_version: str


# ── Application tracker schemas ───────────────────────────────────────────────

class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    profile_id: uuid.UUID
    status: str
    tailored_resume_path: str | None
    cover_letter_path: str | None
    applied_at: datetime | None
    application_reference: str | None
    submission_confirmed: bool
    follow_up_date: datetime | None
    interview_date: datetime | None
    outcome: str | None
    notes: str | None
    discovered_at: datetime
    updated_at: datetime


# ── Dashboard stats schema ────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_companies: int
    total_jobs: int
    open_jobs: int
    eligible_jobs: int
    high_match_jobs: int
    applications_awaiting_review: int
    applications_submitted: int
    applications_total: int
    has_confirmed_profile: bool
    last_discovery_at: datetime | None


# ── Discovery schemas ─────────────────────────────────────────────────────────

class DiscoveryRunRequest(BaseModel):
    max_companies: int | None = Field(default=None, ge=1, le=500)
    fetch_jd: bool = False


class DiscoveryRunResponse(BaseModel):
    status: str
    stats: dict[str, int]
