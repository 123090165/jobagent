from __future__ import annotations

from pydantic import BaseModel, Field

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


class AnalysisQualityReport(BaseModel):
    resume_quality_label: str = "medium"
    jd_quality_label: str = "medium"
    overall_quality_label: str = "medium"
    warnings: list[str] = Field(default_factory=list)
    missing_resume_sections: list[str] = Field(default_factory=list)
    missing_jd_sections: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    resume_profile: ResumeProfile
    job_analysis: JobAnalysis
    match_report: MatchReport
    optimization_result: ResumeOptimizationResult
    project_challenge_report: ProjectChallengeReport
    analysis_quality: AnalysisQualityReport = Field(default_factory=AnalysisQualityReport)
    markdown_report: str
