from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import (
    MatchReport,
    ProjectChallengeReport,
    ResumeOptimizationResult,
)
from app.schemas.resume import ResumeProfile
from app.services.report_service import generate_markdown_report


def generate_report(
    *,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    optimization_result: ResumeOptimizationResult,
    project_challenge_report: ProjectChallengeReport,
) -> str:
    """Generate the final Markdown report from structured agent outputs."""
    return generate_markdown_report(
        resume_profile=resume_profile,
        job_analysis=job_analysis,
        match_report=match_report,
        optimization_result=optimization_result,
        project_challenge_report=project_challenge_report,
    )
