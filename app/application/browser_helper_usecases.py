"""编排 浏览器助手会话 的所有权检查、状态转换、领域服务和持久化操作。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.application.job_search_usecases import analyze_browser_job_capture
from app.repositories.auth_session_repository import (
    AuthSessionRepository,
    auth_session_repository,
)
from app.repositories.browser_job_capture_repository import (
    BrowserJobCaptureRepository,
    browser_job_capture_repository,
)
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.schemas.browser_helper import (
    BrowserHelperContextCatalog,
    BrowserHelperProfileSessionOption,
    BrowserHelperSavedJobOption,
    BrowserHelperSessionCreateResponse,
)
from app.schemas.job_search import (
    BrowserJobCaptureAnalyzeResponse,
    BrowserJobCaptureAnalysisRequest,
    BrowserJobCaptureCreateRequest,
    BrowserJobCaptureCreateResponse,
    BrowserJobCaptureRequest,
)
from app.services.errors import JobAgentError
from app.services.job_search_execution.browser_capture import _capture_summary
from app.services.password_service import generate_auth_token, hash_auth_token


BROWSER_HELPER_SESSION_HOURS = 8
BROWSER_HELPER_SAVED_JOB_LIMIT = 50


def save_browser_job_capture(
    payload: BrowserJobCaptureCreateRequest,
    *,
    user_id: str,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> BrowserJobCaptureCreateResponse:
    record = captures.create(user_id=user_id, payload=payload)
    return BrowserJobCaptureCreateResponse(
        capture_id=record.capture_id,
        capture=_capture_summary(record),
    )


def analyze_saved_browser_job_capture(
    capture_id: str,
    payload: BrowserJobCaptureAnalysisRequest,
    *,
    user_id: str,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> BrowserJobCaptureAnalyzeResponse:
    record = captures.get(user_id=user_id, capture_id=capture_id)
    if record is None:
        raise JobAgentError(
            message="Browser job capture not found.",
            error_code="browser_job_capture_not_found",
            status_code=404,
        )
    return analyze_browser_job_capture(
        BrowserJobCaptureRequest(
            **record.model_dump(
                exclude={
                    "capture_id",
                    "user_id",
                    "created_at",
                    "analysis_mode",
                    "llm_provider",
                    "use_llm",
                }
            ),
            session_id=payload.session_id,
            analysis_mode=payload.analysis_mode,
            llm_provider=payload.llm_provider,
            use_llm=payload.use_llm,
        ),
        user_id=user_id,
    )


def get_browser_helper_context_catalog(
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
) -> BrowserHelperContextCatalog:
    return BrowserHelperContextCatalog(
        saved_jobs=[
            BrowserHelperSavedJobOption(
                saved_job_id=item.saved_job_id,
                title=item.title,
                company=item.company,
                status=item.status,
            )
            for item in saved_jobs.list_by_user(user_id)[:BROWSER_HELPER_SAVED_JOB_LIMIT]
        ]
    )


def create_browser_helper_session(
    *,
    user_id: str,
    user_agent: str | None,
    sessions: AuthSessionRepository = auth_session_repository,
    profile_sessions: ProfileSessionRepository = profile_session_repository,
    resume_profiles: ResumeProfileRepository = resume_profile_repository,
) -> BrowserHelperSessionCreateResponse:
    token = generate_auth_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=BROWSER_HELPER_SESSION_HOURS)
    sessions.create(
        user_id=user_id,
        token_hash=hash_auth_token(token),
        expires_at=expires_at,
        user_agent=user_agent,
        session_scope="browser_helper",
    )
    profiles_by_session = {
        item.source_session_id: item
        for item in resume_profiles.list_by_user(user_id)
        if item.source_session_id
    }
    options: list[BrowserHelperProfileSessionOption] = []
    for session in profile_sessions.list_ready_by_user(user_id):
        profile = profiles_by_session.get(session.session_id)
        options.append(BrowserHelperProfileSessionOption(
            session_id=session.session_id,
            label=profile.name if profile is not None else "Confirmed profile",
            is_default=profile.is_default if profile is not None else False,
        ))
    options.sort(key=lambda item: (not item.is_default, item.label.casefold()))
    return BrowserHelperSessionCreateResponse(
        access_token=token,
        expires_at=expires_at,
        profile_sessions=options,
    )
