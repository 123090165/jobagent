from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport
from app.schemas.resume import ResumeProfile


def analyze_match(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> MatchReport:
    """Compare a structured resume and JD analysis."""
    from app.services.mock_pipeline import mock_match_analysis

    return mock_match_analysis(resume_profile, job_analysis)

