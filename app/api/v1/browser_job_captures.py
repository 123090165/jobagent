"""定义 浏览器职位采集 的 HTTP 接口，并把已验证请求和当前用户交给 application 用例。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_or_browser_helper_user
from app.application.browser_helper_usecases import (
    analyze_saved_browser_job_capture,
    save_browser_job_capture,
)
from app.application.job_search_usecases import analyze_browser_job_capture
from app.schemas.auth import UserAccount
from app.schemas.job_search import (
    BrowserJobCaptureAnalyzeResponse,
    BrowserJobCaptureAnalysisRequest,
    BrowserJobCaptureCreateRequest,
    BrowserJobCaptureCreateResponse,
    BrowserJobCaptureRequest,
)

router = APIRouter(prefix="/api/v1/browser/job-captures", tags=["v4-browser-job-captures"])


@router.post("", response_model=BrowserJobCaptureCreateResponse, status_code=201)
def save_browser_job_capture_endpoint(
    payload: BrowserJobCaptureCreateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> BrowserJobCaptureCreateResponse:
    return save_browser_job_capture(payload, user_id=current_user.user_id)


@router.post("/analyze", response_model=BrowserJobCaptureAnalyzeResponse)
def analyze_browser_job_capture_endpoint(
    payload: BrowserJobCaptureRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> BrowserJobCaptureAnalyzeResponse:
    # [兼容保留] 旧扩展可直接提交未落库 payload；新链路应先保存 capture 再按 ID 分析。
    return analyze_browser_job_capture(payload, user_id=current_user.user_id)


@router.post("/{capture_id}/analyze", response_model=BrowserJobCaptureAnalyzeResponse)
def analyze_saved_browser_job_capture_endpoint(
    capture_id: str,
    payload: BrowserJobCaptureAnalysisRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> BrowserJobCaptureAnalyzeResponse:
    return analyze_saved_browser_job_capture(
        capture_id,
        payload,
        user_id=current_user.user_id,
    )
