"""
Tests for ResumeParser hardening (F14, F15, F16).
- F14: section-end regex must not run under IGNORECASE
- F15: degree regex must not match the word 'be', and highest degree must win (M.Tech before B.Tech)
- F16: percentage must require academic context (ignore random metrics like 'improved by 80%')
"""
import pytest
from app.services.candidate.resume_parser import ResumeParser


class TestResumeParserHardening:
    """Regression tests for F14, F15, F16 parser fixes."""

    def test_skills_section_does_not_truncate_on_lowercase_words(self):
        """F14: Multi-line skills section with lines starting with lowercase words (e.g. 'and')

        must not prematurely end due to IGNORECASE lookahead on [A-Z]{3,}.
        """
        parser = ResumeParser()
        text = (
            "Name: Jane Candidate\n"
            "SKILLS\n"
            "Python, FastAPI\n"
            "and Docker, Kubernetes\n"
            "for cloud deployments\n"
            "PROJECTS\n"
            "Portfolio Website\n"
        )
        skills = parser._extract_skills(text)
        assert "Docker" in skills, f"Docker missing from extracted skills: {skills}"
        assert "Kubernetes" in skills, f"Kubernetes missing from extracted skills: {skills}"

    def test_projects_section_does_not_truncate_on_lowercase_words(self):
        """F14: Projects section must not prematurely end on lowercase words."""
        parser = ResumeParser()
        text = (
            "PROJECTS\n"
            "First Project\n"
            "and its sub-service\n"
            "Second Project\n"
            "EDUCATION\n"
            "B.Tech Computer Science\n"
        )
        projects = parser._extract_projects(text)
        assert projects is not None
        titles = [p["title"] for p in projects]
        assert any("Second Project" in t for t in titles), f"Second Project missing from {titles}"

    def test_degree_does_not_match_word_be(self, monkeypatch):
        """F15: The common English word 'be' must not match 'B.E.' degree."""
        parser = ResumeParser()
        text = (
            "Jane Candidate\n"
            "Aspiring to be a software developer at a top tech firm.\n"
            "Education: Bachelor of Science in Mathematics\n"
        )
        monkeypatch.setattr(parser, "_extract_text", lambda _: text)
        import io
        import asyncio
        result = asyncio.run(parser.parse_pdf(io.BytesIO(b"dummy")))
        assert result.get("degree") != "B.E.", f"Degree was incorrectly parsed as 'B.E.' from word 'be': {result.get('degree')}"
        assert result.get("degree") == "B.Sc.", f"Expected B.Sc., got {result.get('degree')}"

    def test_highest_degree_wins_mtech_over_btech(self, monkeypatch):
        """F15: Highest degree must win when multiple degrees are listed (M.Tech before B.Tech)."""
        parser = ResumeParser()
        text = (
            "Jane Candidate\n"
            "Education:\n"
            "B.Tech in Information Technology, 2020\n"
            "M.Tech in Computer Science, 2022\n"
        )
        monkeypatch.setattr(parser, "_extract_text", lambda _: text)
        import io
        import asyncio
        result = asyncio.run(parser.parse_pdf(io.BytesIO(b"dummy")))
        assert result.get("degree") == "M.Tech", f"Expected M.Tech to win over B.Tech, got {result.get('degree')}"

    def test_percentage_requires_academic_context(self, monkeypatch):
        """F16: Metric percentages like 'improved performance by 85%' must not be treated as academic percentage."""
        parser = ResumeParser()
        text_without_academic = (
            "Jane Candidate\n"
            "Experience:\n"
            "Improved database query efficiency by 85% across all endpoints.\n"
            "Increased unit test coverage to 92%.\n"
        )
        monkeypatch.setattr(parser, "_extract_text", lambda _: text_without_academic)
        import io
        import asyncio
        result = asyncio.run(parser.parse_pdf(io.BytesIO(b"dummy")))
        assert result.get("percentage") is None, f"Non-academic percentage was parsed as candidate percentage: {result.get('percentage')}"

    def test_percentage_extracted_with_academic_context(self, monkeypatch):
        """F16: Academic percentages like 'Aggregate: 82.5%' or '12th Board: 88%' must be extracted."""
        parser = ResumeParser()
        text_with_academic = (
            "Jane Candidate\n"
            "Education:\n"
            "Class 12th Board: 88.5%\n"
            "B.Tech Aggregate: 79%\n"
        )
        monkeypatch.setattr(parser, "_extract_text", lambda _: text_with_academic)
        import io
        import asyncio
        result = asyncio.run(parser.parse_pdf(io.BytesIO(b"dummy")))
        assert result.get("percentage") in (88.5, 79.0), f"Academic percentage was not extracted: {result.get('percentage')}"

