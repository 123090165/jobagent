from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ResumeOptimizationResult
from app.schemas.resume import ResumeProfile


def optimize_resume(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> ResumeOptimizationResult:
    """Generate resume optimization suggestions without inventing experience."""
    from app.services.mock_pipeline import mock_resume_optimization

    return mock_resume_optimization(
        resume_text.strip(),
        resume_profile,
        job_analysis,
        match_report,
    )

