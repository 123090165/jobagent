from __future__ import annotations

from pydantic import BaseModel

from app.schemas.job import JobAnalysis
from app.schemas.match import (
    MatchReport,
    ProjectChallengeReport,
    ResumeOptimizationResult,
)
from app.schemas.resume import ResumeProfile


class AnalysisRequest(BaseModel):
    resume_text: str
    jd_text: str


class FinalReport(BaseModel):
    resume_profile: ResumeProfile
    job_analysis: JobAnalysis
    match_report: MatchReport
    optimization_result: ResumeOptimizationResult
    project_challenge_report: ProjectChallengeReport
    markdown_report: str
