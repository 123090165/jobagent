from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError


class JobSearchPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    must_have_signals: list[str] = Field(default_factory=list)
    avoid_signals: list[str] = Field(default_factory=list)
    ranking_policy: str
    mode: Literal["deterministic", "llm", "fallback"]
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)


def build_search_plan(
    confirmed_profile: ConfirmedProfile,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchPlan:
    deterministic = _build_deterministic_plan(confirmed_profile)
    if not use_llm:
        return deterministic

    if llm_service is None:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": "llm_service_unavailable",
                "quality_warnings": _dedupe(deterministic.quality_warnings + ["LLM planning unavailable. Used deterministic search plan."]),
            }
        )

    try:
        payload = llm_service.chat_completion_json(
            system_prompt=(
                "You are a job search planning assistant. "
                "Only expand and refine search queries from the provided confirmed profile. "
                "Do not invent user experience, employers, industries, or credentials. "
                "Return JSON with queries, locations, target_roles, must_have_signals, avoid_signals, ranking_policy, and quality_warnings."
            ),
            user_prompt=(
                "Confirmed profile JSON:\n"
                f"{json.dumps(confirmed_profile.model_dump(mode='json'), ensure_ascii=False)}"
            ),
        )
        plan = JobSearchPlan.model_validate(
            {
                "queries": payload.get("queries", []),
                "locations": payload.get("locations", []),
                "target_roles": payload.get("target_roles", []),
                "must_have_signals": payload.get("must_have_signals", []),
                "avoid_signals": payload.get("avoid_signals", []),
                "ranking_policy": payload.get("ranking_policy") or deterministic.ranking_policy,
                "mode": "llm",
                "fallback_reason": None,
                "quality_warnings": payload.get("quality_warnings", []),
            }
        )
        return _normalize_plan(plan, fallback=deterministic)
    except (LLMServiceError, ValueError, TypeError) as exc:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": type(exc).__name__,
                "quality_warnings": _dedupe(
                    deterministic.quality_warnings
                    + [f"LLM planning fallback triggered: {type(exc).__name__}."]
                ),
            }
        )


def _build_deterministic_plan(confirmed_profile: ConfirmedProfile) -> JobSearchPlan:
    target_roles = _dedupe(confirmed_profile.target_roles)
    keywords = _dedupe(confirmed_profile.search_keywords + confirmed_profile.core_skills)
    locations = _dedupe(confirmed_profile.preferred_locations)
    queries: list[str] = []

    role_seed = target_roles[:4] or ["Software Engineer"]
    keyword_seed = keywords[:6]
    for role in role_seed:
        base_query = role
        if keyword_seed:
            base_query = f"{role} {' '.join(keyword_seed[:3])}"
        queries.append(base_query.strip())

    if not queries and keyword_seed:
        queries.append(" ".join(keyword_seed[:5]))
    if not queries:
        queries.append("Software Engineer")

    warnings: list[str] = []
    if not confirmed_profile.preferred_locations:
        warnings.append("No preferred locations found; search will include remote-friendly defaults.")
    if not confirmed_profile.search_keywords:
        warnings.append("Search keywords were sparse; core skills were used to build the plan.")

    return JobSearchPlan(
        queries=_dedupe(queries),
        locations=locations,
        target_roles=target_roles,
        must_have_signals=keyword_seed,
        avoid_signals=_dedupe(confirmed_profile.risks)[:5],
        ranking_policy="Prefer target role overlap, skill overlap, and clear source metadata.",
        mode="deterministic",
        fallback_reason=None,
        quality_warnings=warnings,
    )


def _normalize_plan(plan: JobSearchPlan, *, fallback: JobSearchPlan) -> JobSearchPlan:
    queries = _dedupe(plan.queries) or fallback.queries
    locations = _dedupe(plan.locations) or fallback.locations
    target_roles = _dedupe(plan.target_roles) or fallback.target_roles
    must_have = _dedupe(plan.must_have_signals) or fallback.must_have_signals
    avoid = _dedupe(plan.avoid_signals)
    return plan.model_copy(
        update={
            "queries": queries,
            "locations": locations,
            "target_roles": target_roles,
            "must_have_signals": must_have,
            "avoid_signals": avoid,
            "quality_warnings": _dedupe(plan.quality_warnings),
        }
    )


def _dedupe(values: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items
