from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import MarkdownReportResponse, ReportGenerateRequest
from app.services.report_service import generate_markdown_report

router = APIRouter(tags=["reports"])


@router.post("/reports/generate", response_model=MarkdownReportResponse)
def generate_report(request: ReportGenerateRequest) -> MarkdownReportResponse:
    markdown_report = generate_markdown_report(
        resume_profile=request.resume_profile,
        job_analysis=request.job_analysis,
        match_report=request.match_report,
        optimization_result=request.optimization_result,
        project_challenge_report=request.project_challenge_report,
    )
    return MarkdownReportResponse(markdown_report=markdown_report)
