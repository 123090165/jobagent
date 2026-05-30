from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import ProjectChallengeReport
from app.schemas.resume import ResumeProfile


def generate_project_challenges(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> ProjectChallengeReport:
    """Generate interview challenge questions from resume and JD context."""
    from app.services.mock_pipeline import mock_project_challenge

    return mock_project_challenge(resume_profile, job_analysis)

