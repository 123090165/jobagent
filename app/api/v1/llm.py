from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from app.schemas.llm import LLMStatusResponse
from app.services.llm_provider import resolve_llm_provider_for_switch

router = APIRouter(prefix="/api/v1/llm", tags=["v4-llm"])


@router.get("/status", response_model=LLMStatusResponse)
def get_llm_status_endpoint(
    use_deepseek: bool = Query(default=False),
) -> LLMStatusResponse:
    resolution = resolve_llm_provider_for_switch(use_deepseek=use_deepseek)
    return LLMStatusResponse(
        provider=resolution.provider,
        configured=resolution.configured,
        model=resolution.model,
        base_url=resolution.base_url,
        reason=resolution.reason,
    )
