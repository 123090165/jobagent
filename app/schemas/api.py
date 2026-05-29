from __future__ import annotations

from pydantic import BaseModel

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ProjectChallengeReport, ResumeOptimizationResult
from app.schemas.report import FinalReport
from app.schemas.resume import ResumeProfile


class HealthResponse(BaseModel):
    status: str
    version: str


class FullAnalysisRequest(BaseModel):
    resume_text: str
    jd_text: str
    use_llm_jd: bool = False
    save_result: bool = False


class FullAnalysisResponse(FinalReport):
    record_id: int | None = None


class ResumeParseRequest(BaseModel):
    resume_text: str


class JDAnalysisRequest(BaseModel):
    jd_text: str
    use_llm: bool = False


class MatchAnalysisRequest(BaseModel):
    resume_profile: ResumeProfile
    job_analysis: JobAnalysis


class ReportGenerateRequest(BaseModel):
    resume_profile: ResumeProfile
    job_analysis: JobAnalysis
    match_report: MatchReport
    optimization_result: ResumeOptimizationResult
    project_challenge_report: ProjectChallengeReport


class MarkdownReportResponse(BaseModel):
    markdown_report: str


class AnalysisRecordResponse(FullAnalysisResponse):
    id: int
    created_at: str


class AnalysisRecordSummary(BaseModel):
    id: int
    created_at: str
    job_title: str | None = None
    company: str | None = None
    overall_score: float


class JobPostingSummary(BaseModel):
    id: int
    created_at: str
    job_title: str | None = None
    company: str | None = None
    keyword_text: str | None = None
    analysis_count: int = 0


class JobPostingResponse(BaseModel):
    id: int
    created_at: str
    raw_jd: str
    job_analysis: JobAnalysis
    analysis_count: int = 0
