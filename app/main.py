from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_analyze import router as analyze_router
from app.api.routes_applications import router as applications_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_match import router as match_router
from app.api.routes_records import router as records_router
from app.api.routes_reports import router as reports_router
from app.api.routes_resume import router as resume_router
from app.schemas.api import HealthResponse
from app.services.mock_pipeline import run_mock_pipeline

API_VERSION = "0.3.0"


def create_app() -> FastAPI:
    api = FastAPI(
        title="JobAgent API",
        version=API_VERSION,
        description="Resume-JD matching, resume optimization, and interview preparation API.",
    )

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION)

    api.include_router(analyze_router)
    api.include_router(resume_router)
    api.include_router(jobs_router)
    api.include_router(match_router)
    api.include_router(reports_router)
    api.include_router(records_router)
    api.include_router(applications_router)
    return api


app = create_app()


def analyze_resume_and_jd(resume_text: str, jd_text: str):
    """Run the current v0.1 mock analysis pipeline."""
    return run_mock_pipeline(resume_text=resume_text, jd_text=jd_text)


def demo_cli() -> None:
    sample_resume = "Python 后端开发，做过 FastAPI、Pydantic、Streamlit 项目。"
    sample_jd = "招聘 Python 后端工程师，要求 FastAPI、SQL、REST API，有 LLM 应用经验优先。"
    result = analyze_resume_and_jd(sample_resume, sample_jd)
    print(result.markdown_report)


if __name__ == "__main__":
    demo_cli()
