from __future__ import annotations

from fastapi import APIRouter

from app.application.job_search_usecases import analyze_browser_job_capture
from app.schemas.job_search import (
    BrowserJobCaptureAnalyzeResponse,
    BrowserJobCaptureRequest,
)

router = APIRouter(prefix="/api/v1/browser/job-captures", tags=["v4-browser-job-captures"])


@router.post("/analyze", response_model=BrowserJobCaptureAnalyzeResponse)
def analyze_browser_job_capture_endpoint(
    payload: BrowserJobCaptureRequest,
) -> BrowserJobCaptureAnalyzeResponse:
    return analyze_browser_job_capture(payload)
