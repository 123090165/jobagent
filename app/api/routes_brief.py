from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import (
    BriefFromSearchRequest,
    BriefRerankRequest,
    BriefRunFromSearchRequest,
    BriefRunResponse,
    ProfileSearchPlanRequest,
)
from app.schemas.brief import JobBriefReport
from app.schemas.profile_review import ProfileSearchPlan
from app.services.batch_brief_service import build_brief_from_search, build_profile_search_plan
from app.services.brief_rerank_service import rerank_brief_run
from app.services.brief_run_storage_service import get_brief_run, save_brief_run
from app.services.errors import JobAgentError

router = APIRouter(tags=["brief"])


@router.post("/brief/search-plan", response_model=ProfileSearchPlan)
def preview_profile_search_plan(request: ProfileSearchPlanRequest) -> ProfileSearchPlan:
    return build_profile_search_plan(
        request.query,
        request.profile_context,
    )


@router.post("/brief/from-search", response_model=JobBriefReport)
def generate_brief_from_search(request: BriefFromSearchRequest) -> JobBriefReport:
    return build_brief_from_search(
        resume_text=request.resume_text,
        query=request.query,
        provider=request.provider,
        limit=request.limit,
        use_llm_jd=request.use_llm_jd,
        profile_context=request.profile_context,
    )


@router.post("/brief/runs/from-search", response_model=BriefRunResponse)
def generate_brief_run_from_search(request: BriefRunFromSearchRequest) -> BriefRunResponse:
    brief = build_brief_from_search(
        resume_text=request.resume_text,
        query=request.query,
        provider=request.provider,
        limit=request.limit,
        use_llm_jd=request.use_llm_jd,
        profile_context=request.profile_context,
    )
    run_id = save_brief_run(brief, request.resume_text)
    return BriefRunResponse(run_id=run_id, brief=brief)


@router.get("/brief/runs/{run_id}", response_model=BriefRunResponse)
def get_saved_brief_run(run_id: str) -> BriefRunResponse:
    stored_run = get_brief_run(run_id)
    if stored_run is None:
        raise JobAgentError("Brief run not found", "brief_run_not_found", status_code=404)
    return BriefRunResponse(
        run_id=stored_run["run_id"],
        brief=JobBriefReport.model_validate(stored_run["brief"]),
    )


@router.post("/brief/runs/{run_id}/rerank", response_model=JobBriefReport)
def rerank_saved_brief_run(run_id: str, request: BriefRerankRequest) -> JobBriefReport:
    return rerank_brief_run(
        run_id=run_id,
        require_full_jd=request.require_full_jd,
        exclude_external_link_only=request.exclude_external_link_only,
        location_keywords=request.location_keywords,
        include_keywords=request.include_keywords,
        exclude_keywords=request.exclude_keywords,
        min_fit_score=request.min_fit_score,
        limit=request.limit,
    )
