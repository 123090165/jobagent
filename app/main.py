from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.env_loader import load_local_env
from app.api.v1.auth import router as auth_v1_router
from app.api.v1.browser_job_captures import router as browser_job_captures_v1_router
from app.api.v1.confirmed_profiles import router as confirmed_profiles_v1_router
from app.api.v1.job_search_providers import router as job_search_providers_v1_router
from app.api.v1.job_search_runs import router as job_search_runs_v1_router
from app.api.v1.llm import router as llm_v1_router
from app.api.v1.profile_drafts import router as profile_drafts_v1_router
from app.api.v1.resume_profiles import router as resume_profiles_v1_router
from app.api.v1.profile_sessions import router as profile_sessions_v1_router
from app.api.v1.saved_jobs import router as saved_jobs_v1_router
from app.schemas.api import HealthResponse
from app.services.errors import JobAgentError

API_VERSION = "0.3.0"
DEFAULT_CORS_ALLOW_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def _resolve_cors_allow_origins() -> list[str]:
    configured = os.getenv("JOBAGENT_CORS_ALLOW_ORIGINS", "")
    origins = [
        item.strip()
        for item in configured.split(",")
        if item.strip()
    ]
    return origins or DEFAULT_CORS_ALLOW_ORIGINS


def create_app() -> FastAPI:
    load_local_env()

    api = FastAPI(
        title="JobAgent API",
        version=API_VERSION,
        description="ProfileSession resume intake, review, draft, confirmation, job search, and job brief API.",
    )
    allowed_origins = _resolve_cors_allow_origins()
    if allowed_origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
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
    api.include_router(auth_v1_router)
    api.include_router(resume_profiles_v1_router)
    api.include_router(saved_jobs_v1_router)
    api.include_router(profile_drafts_v1_router)
    api.include_router(confirmed_profiles_v1_router)
    api.include_router(job_search_runs_v1_router)
    api.include_router(job_search_providers_v1_router)
    api.include_router(browser_job_captures_v1_router)
    api.include_router(llm_v1_router)
    return api


app = create_app()
