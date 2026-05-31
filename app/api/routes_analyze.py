from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import FullAnalysisRequest, FullAnalysisResponse
from app.services.errors import JobAgentError
from app.services.storage_service import save_final_report
from app.workflows.job_analysis_workflow import run_job_analysis_workflow

router = APIRouter(tags=["analyze"])


@router.post("/analyze/full", response_model=FullAnalysisResponse)
def analyze_full(request: FullAnalysisRequest) -> FullAnalysisResponse:
    try:
        workflow_result = run_job_analysis_workflow(
            resume_text=request.resume_text,
            jd_text=request.jd_text,
            use_llm_jd=request.use_llm_jd,
            use_llm_resume_optimize=request.use_llm_resume_optimize,
        )
    except ValueError as exc:
        raise JobAgentError(str(exc), "analysis_input_invalid") from exc

    result = workflow_result.final_report
    workflow_steps = [step.model_dump() for step in workflow_result.state.steps]
    record_id = (
        save_final_report(result, workflow_steps=workflow_steps)
        if request.save_result
        else None
    )
    return FullAnalysisResponse(
        **result.model_dump(),
        record_id=record_id,
        workflow_steps=workflow_steps,
    )
