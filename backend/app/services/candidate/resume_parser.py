"""
PDF resume parser — extracts candidate information from uploaded resumes.

IMPORTANT: This parser only extracts what is explicitly present in the PDF.
It never invents, infers, or fabricates any information.
All extracted fields are returned as-is for user review and confirmation.
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-\(\)]{7,14}\d)")
URL_RE = re.compile(r"https?://[^\s,;\"'<>()]+")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"github\.com/[\w\-]+", re.IGNORECASE)
CGPA_RE = re.compile(r"\b([0-9]\.[0-9]{1,2})\s*/\s*(4\.0|10\.0|10)\b", re.IGNORECASE)
ACADEMIC_PERCENTAGE_RE = re.compile(
    r"(?:"
    r"(?:marks|score|aggregate|percentage|academics|academic|class\s*(?:10|12|x|xii)|10th|12th|board|secondary|higher\s+secondary)"
    r"[^\n\r\.\;]{0,40}?"
    r"([5-9][0-9](?:\.\d+)?|100(?:\.\d+)?)\s*%"
    r"|"
    r"([5-9][0-9](?:\.\d+)?|100(?:\.\d+)?)\s*%"
    r"[^\n\r\.\;]{0,40}?"
    r"(?:marks|score|aggregate|percentage|academics|academic|in\s+(?:10th|12th|class\s*(?:10|12|x|xii)|board))"
    r")",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


class ResumeParser:
    """
    Extracts structured candidate information from a PDF resume.

    All extracted fields require user review and confirmation.
    Confidence scores indicate extraction reliability, not qualifications.
    """

    async def parse_pdf(self, pdf_file: BytesIO) -> dict[str, Any]:
        """
        Parse a PDF and extract candidate fields.
        Returns a dict suitable for populating CandidateProfile fields.
        All values are nullable; missing fields are null, not inferred.
        """
        text = self._extract_text(pdf_file)
        if not text:
            return {
                "_warnings": ["Could not extract text from PDF. Please enter your details manually."],
                "_raw_text": None,
            }

        extracted: dict[str, Any] = {}
        warnings: list[str] = []

        # ── Contact info ──────────────────────────────────────────────────
        emails = EMAIL_RE.findall(text)
        extracted["email"] = emails[0] if emails else None
        if len(emails) > 1:
            warnings.append(f"Multiple emails found: {emails}. Using first.")

        phones = PHONE_RE.findall(text)
        clean_phones = [re.sub(r"[\s\-\(\)]", "", p) for p in phones if len(re.sub(r"\D", "", p)) >= 10]
        extracted["phone"] = clean_phones[0] if clean_phones else None

        # Name: heuristic — first non-empty line before email
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        name_candidate = lines[0] if lines else None
        # Validate it looks like a name (2-5 words, mostly alpha)
        if name_candidate and len(name_candidate.split()) <= 5 and re.match(r"^[A-Za-z\s\.\-]+$", name_candidate):
            extracted["full_name"] = name_candidate
        else:
            extracted["full_name"] = None
            warnings.append("Could not reliably extract name from first line. Please enter manually.")

        # URLs
        linkedin_match = LINKEDIN_RE.search(text)
        extracted["linkedin_url"] = f"https://{linkedin_match.group()}" if linkedin_match else None
        github_match = GITHUB_RE.search(text)
        extracted["github_url"] = f"https://{github_match.group()}" if github_match else None

        # Location
        loc_match = re.search(
            r"(?:Location|Address|City)[:\s]+([A-Za-z\s,]+?)(?=\n|\||\Z)",
            text,
            re.IGNORECASE,
        )
        if loc_match:
            loc = loc_match.group(1).strip()
            extracted["location"] = loc if 2 <= len(loc) <= 80 else None
        else:
            city_match = re.search(
                r"\b(Bengaluru|Bangalore|Hyderabad|Pune|Mumbai|Delhi|Noida|Gurgaon|Gurugram|Chennai|Kolkata)\b(?:[,\s]+(?:Karnataka|Maharashtra|Telangana|Tamil Nadu|Haryana|West Bengal|India))?",
                text,
                re.IGNORECASE,
            )
            extracted["location"] = city_match.group(0).strip() if city_match else None

        # ── Education ─────────────────────────────────────────────────────
        cgpa_matches = CGPA_RE.findall(text)
        if cgpa_matches:
            val, scale = cgpa_matches[0]
            extracted["cgpa"] = float(val)
            extracted["cgpa_scale"] = float(scale)
        else:
            extracted["cgpa"] = None
            extracted["cgpa_scale"] = None

        percentage_matches = []
        for m in ACADEMIC_PERCENTAGE_RE.finditer(text):
            val = m.group(1) or m.group(2)
            if val:
                percentage_matches.append(float(val))
        extracted["percentage"] = percentage_matches[0] if percentage_matches else None

        # Graduation year: most recent 20xx year in context of "batch" / "pass" / "grad"
        grad_context = re.findall(
            r"(?:batch|pass(?:ing|ed|out)?|grad(?:uat(?:ed|ion))?|class of)[^\n]{0,30}(20\d{2})",
            text,
            re.IGNORECASE,
        )
        if grad_context:
            extracted["graduation_year"] = int(grad_context[-1])
        else:
            all_years = YEAR_RE.findall(text)
            years = [int(y) for y in all_years if 2020 <= int(y) <= 2030]
            extracted["graduation_year"] = max(years) if years else None
            if years:
                warnings.append("Graduation year inferred from year mentions. Please verify.")

        # Degree: highest degree wins (Masters/Doctorate prioritized over Bachelors).
        # BE regex must not match the common English word 'be'.
        degree_patterns = [
            (r"\b(Ph\.?D\.?|Doctor\s+of\s+Philosophy)\b", "Ph.D."),
            (r"\b(M\.?Tech|Master\s+of\s+Technology)\b", "M.Tech"),
            (r"(?i:\bMaster\s+of\s+Engineering\b|\bM\.E\.\b|\bM\.E\b)|\bME\b", "M.E."),
            (r"\b(M\.?Sc|Master\s+of\s+Science)\b", "M.Sc."),
            (r"\b(MBA|Master\s+of\s+Business)\b", "MBA"),
            (r"\b(MCA)\b", "MCA"),
            (r"\b(B\.?Tech|Bachelor\s+of\s+Technology)\b", "B.Tech"),
            (r"(?i:\bBachelor\s+of\s+Engineering\b|\bB\.E\.\b|\bB\.E\b)|\bBE\b", "B.E."),
            (r"\b(B\.?Sc|Bachelor\s+of\s+Science)\b", "B.Sc."),
            (r"\b(BCA)\b", "BCA"),
        ]
        extracted["degree"] = None
        for pattern, label in degree_patterns:
            if re.search(pattern, text, re.IGNORECASE if "BE" not in pattern and "ME" not in pattern else 0):
                extracted["degree"] = label
                break

        # ── Skills ────────────────────────────────────────────────────────
        skills = self._extract_skills(text)
        extracted["skills"] = skills if skills else None
        if not skills:
            warnings.append("Could not automatically extract skills list. Please add manually.")

        # ── Experience ────────────────────────────────────────────────────
        extracted["work_experience"] = self._extract_experience(text)
        extracted["projects"] = self._extract_projects(text)

        # ── Raw text (for manual review, truncated) ───────────────────────
        extracted["_raw_text_preview"] = text[:2000]
        extracted["_warnings"] = warnings
        extracted["_extraction_confidence"] = self._estimate_confidence(extracted)

        logger.info(
            "resume_parsed",
            has_email=bool(extracted.get("email")),
            has_name=bool(extracted.get("full_name")),
            skills_count=len(extracted.get("skills") or []),
            warnings_count=len(warnings),
        )

        return extracted

    def _extract_text(self, pdf_file: BytesIO) -> str:
        """Extract plain text from a PDF using pdfplumber (primary) or pypdf (fallback)."""
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
        except Exception as exc:
            logger.warning("pdfplumber_failed", error=str(exc))
            try:
                pdf_file.seek(0)
                from pypdf import PdfReader
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
            except Exception as exc2:
                logger.error("pdf_extract_failed", error=str(exc2))
        return text.strip()

    def _extract_skills(self, text: str) -> list[str]:
        """Extract skills from the Skills/Technologies section."""
        # Look for a skills section.
        # Section header uses case-insensitive group (?i:...),
        # but section boundary lookahead strictly matches uppercase [A-Z]{3,} without IGNORECASE (F14).
        skills_section = re.search(
            r"(?i:SKILLS|TECHNICAL SKILLS|TECHNOLOGIES|TECH STACK)[:\s]*\n(.*?)(?=\n[A-Z]{3,}|\Z)",
            text,
            re.DOTALL,
        )
        if not skills_section:
            return []

        section_text = skills_section.group(1)
        # Split by common delimiters
        raw_skills = re.split(r"[,|•·\n\t]+|(?:\s+and\s+)|\s*&\s*", section_text)
        skills = []
        for s in raw_skills:
            s = s.strip().strip("*-•·")
            if s.lower().startswith("and "):
                s = s[4:].strip()
            if s and 2 <= len(s) <= 50 and not s.isnumeric():
                skills.append(s)
        return skills[:60]  # Reasonable cap

    def _extract_experience(self, text: str) -> list[dict] | None:
        """Extract work experience entries (minimal — title, company, dates)."""
        entries = []
        # Simple pattern: look for date ranges near company-like text
        date_range_re = re.compile(
            r"([A-Za-z]+\.?\s+\d{4})\s*[-–—]\s*([A-Za-z]+\.?\s+\d{4}|Present|Current|Now)",
            re.IGNORECASE,
        )
        matches = list(date_range_re.finditer(text))
        for m in matches[:10]:  # Cap at 10 entries
            start_pos = max(0, m.start() - 200)
            end_pos = min(len(text), m.end() + 200)
            context = text[start_pos:end_pos]
            entries.append({
                "start_date": m.group(1),
                "end_date": m.group(2),
                "context_snippet": context[:300],
                "_requires_review": True,
            })
        return entries if entries else None

    def _extract_projects(self, text: str) -> list[dict] | None:
        """Extract project titles from a Projects section."""
        # Section boundary lookahead strictly matches uppercase [A-Z]{3,} without IGNORECASE (F14).
        projects_section = re.search(
            r"(?i:PROJECTS?|PERSONAL PROJECTS?|KEY PROJECTS?)[:\s]*\n(.*?)(?=\n[A-Z]{3,}|\Z)",
            text,
            re.DOTALL,
        )
        if not projects_section:
            return None

        section_text = projects_section.group(1)
        # Look for lines that seem like project titles (start with capital, not too long)
        project_lines = [
            l.strip("•·-* ")
            for l in section_text.splitlines()
            if l.strip() and 5 < len(l.strip()) < 100
        ]
        projects = [{"title": p, "_requires_review": True} for p in project_lines[:20]]
        return projects if projects else None

    def _estimate_confidence(self, extracted: dict) -> float:
        """Rough confidence score based on how many key fields were found."""
        key_fields = ["full_name", "email", "degree", "graduation_year", "skills"]
        found = sum(1 for f in key_fields if extracted.get(f))
        return round(found / len(key_fields), 2)
