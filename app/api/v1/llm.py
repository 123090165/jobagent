from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from app.schemas.llm import LLMStatusResponse
from app.services.llm_provider import resolve_llm_provider, resolve_llm_provider_for_switch

router = APIRouter(prefix="/api/v1/llm", tags=["v4-llm"])


@router.get("/status", response_model=LLMStatusResponse)
def get_llm_status_endpoint(
    provider: str | None = Query(default=None),
    use_deepseek: bool | None = Query(default=None),
) -> LLMStatusResponse:
    if provider is not None:
        resolution = resolve_llm_provider(provider)
    elif use_deepseek is not None:
        resolution = resolve_llm_provider_for_switch(use_deepseek=use_deepseek)
    else:
        resolution = resolve_llm_provider()
    return LLMStatusResponse(
        provider=resolution.provider,
        configured=resolution.configured,
        model=resolution.model,
        base_url=resolution.base_url,
        reason=resolution.reason,
    )
