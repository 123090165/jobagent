from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.confirmed_profiles import router as confirmed_profiles_v1_router
from app.api.v1.job_search_providers import router as job_search_providers_v1_router
from app.api.v1.job_search_runs import router as job_search_runs_v1_router
from app.api.v1.llm import router as llm_v1_router
from app.api.v1.profile_drafts import router as profile_drafts_v1_router
from app.api.v1.profile_sessions import router as profile_sessions_v1_router
from app.schemas.api import HealthResponse
from app.services.errors import JobAgentError

API_VERSION = "0.3.0"


def create_app() -> FastAPI:
    api = FastAPI(
        title="JobAgent API",
        version=API_VERSION,
        description="ProfileSession resume intake, review, draft, confirmation, job search, and job brief API.",
    )

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION)

    @api.exception_handler(JobAgentError)
    async def jobagent_error_handler(
        request: Request,
        exc: JobAgentError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    api.include_router(profile_sessions_v1_router)
    api.include_router(profile_drafts_v1_router)
    api.include_router(confirmed_profiles_v1_router)
    api.include_router(job_search_runs_v1_router)
    api.include_router(job_search_providers_v1_router)
    api.include_router(llm_v1_router)
    return api


app = create_app()
