from __future__ import annotations

from app.schemas.resume import ResumeProfile


def parse_resume(resume_text: str) -> ResumeProfile:
    """Parse resume text into the shared ResumeProfile schema."""
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise ValueError("resume_text cannot be empty")

    from app.services.mock_pipeline import mock_resume_parse

    return mock_resume_parse(normalized_resume)

