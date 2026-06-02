from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ProjectChallengeReport, ResumeOptimizationResult
from app.schemas.report import FinalReport
from app.schemas.resume import ResumeProfile


class HealthResponse(BaseModel):
    status: str
    version: str


class WorkflowStepTraceResponse(BaseModel):
    workflow_run_id: str | None = None
    name: str
    status: str
    mode: str
    summary: str
    duration_ms: float = 0.0
    fallback_reason: str | None = None
    guardrails: list[str] = Field(default_factory=list)


class FullAnalysisRequest(BaseModel):
    resume_text: str
    jd_text: str
    use_langgraph_workflow: bool = False
    use_llm_jd: bool = False
    use_llm_resume_optimize: bool = False
    use_llm_project_challenge: bool = False
    save_result: bool = False


class FullAnalysisResponse(FinalReport):
    record_id: int | None = None
    workflow_steps: list[WorkflowStepTraceResponse] = Field(default_factory=list)


class SearchJobsRequest(BaseModel):
    query: str
    provider: str = "mock"
    limit: int = 5


class BriefFromSearchRequest(BaseModel):
    resume_text: str
    query: str
    provider: str = "mock"
    limit: int = 5
    use_llm_jd: bool = False


class ResumeParseRequest(BaseModel):
    resume_text: str


class ResumeFileParseResponse(BaseModel):
    filename: str
    file_type: str
    extracted_text: str
    resume_profile: ResumeProfile


class JDAnalysisRequest(BaseModel):
    jd_text: str
    use_llm: bool = False


class JDUrlImportRequest(BaseModel):
    url: str


class JDUrlImportResponse(BaseModel):
    url: str
    extracted_text: str
    warning: str | None = None


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
