from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import JobSearchIntent
from app.services.job_search_intent import (
    build_queries_from_intent,
    build_search_intent,
    is_generic_tool_term,
)
from app.services.llm_provider import JSONChatLLM


class JobSearchPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    must_have_signals: list[str] = Field(default_factory=list)
    avoid_signals: list[str] = Field(default_factory=list)
    ranking_policy: str
    search_intent: JobSearchIntent | None = None
    mode: Literal["deterministic", "llm", "fallback"]
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, object] = Field(default_factory=dict)


def build_search_plan(
    confirmed_profile: ConfirmedProfile,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchPlan:
    total_start = time.perf_counter()
    intent_start = time.perf_counter()
    intent = build_search_intent(
        confirmed_profile,
        use_llm=use_llm,
        llm_service=llm_service,
    )
    intent_ms = _elapsed_ms(intent_start)
    assembly_start = time.perf_counter()
    plan = _build_plan_from_intent(confirmed_profile, intent)
    assembly_ms = _elapsed_ms(assembly_start)
    return plan.model_copy(
        update={
            "diagnostics": {
                "timings_ms": {
                    "intent_extraction": intent_ms,
                    "plan_assembly": assembly_ms,
                    "total": _elapsed_ms(total_start),
                },
                "payload_stats": {
                    "query_count": len(plan.queries),
                    "target_role_count": len(plan.target_roles),
                    "ranking_signal_count": len(plan.must_have_signals),
                    "planning_mode": plan.mode,
                },
            }
        }
    )


def _build_plan_from_intent(
    confirmed_profile: ConfirmedProfile,
    intent: JobSearchIntent,
) -> JobSearchPlan:
    target_roles = _dedupe(intent.role_titles or confirmed_profile.target_roles)
    locations = _dedupe(confirmed_profile.preferred_locations)
    queries = build_queries_from_intent(intent)

    if not queries:
        fallback_query = " ".join(
            _dedupe(
                target_roles[:1]
                + intent.role_families[:1]
                + intent.industry_domains[:2]
                + intent.evidence_skills[:2]
            )
        ).strip()
        queries.append(fallback_query or "Internship")

    warnings: list[str] = []
    if not confirmed_profile.preferred_locations:
        warnings.append("No preferred locations found; search will include remote-friendly defaults.")
    if not confirmed_profile.search_keywords and not intent.industry_domains and not intent.evidence_skills:
        warnings.append("Search keywords were sparse; core skills were used to build the plan.")
    warnings = _dedupe(warnings + intent.quality_warnings)

    return JobSearchPlan(
        queries=_dedupe(queries),
        locations=locations,
        target_roles=target_roles,
        must_have_signals=_dedupe(
            intent.role_titles
            + intent.industry_domains
            + intent.evidence_skills
            + intent.generic_tools
        )[:14],
        avoid_signals=_dedupe(intent.negative_signals or confirmed_profile.risks)[:8],
        ranking_policy=(
            "Prefer profile-derived role overlap, domain overlap, distinctive evidence skills, "
            "constraint fit, and clear source metadata. Treat generic tools as weak supporting signals."
        ),
        search_intent=intent,
        mode=intent.mode,
        fallback_reason=intent.fallback_reason,
        quality_warnings=warnings,
    )


def build_focused_provider_queries(target_roles: list[str], search_signal_terms: list[str]) -> list[str]:
    keyword_seed = _dedupe(search_signal_terms)[:6]
    role_seed = _dedupe(target_roles)[:4]
    if not role_seed:
        return [" ".join(keyword_seed[:5])] if keyword_seed else []

    queries: list[str] = []
    for role in role_seed:
        role_terms = [
            term
            for term in keyword_seed
            if not _overlaps_target_role(term, [role])
            and not is_generic_tool_term(term)
        ]
        base_query = role
        if role_terms:
            base_query = f"{role} {' '.join(role_terms[:2])}"
        queries.append(base_query.strip())
    return _dedupe(queries)


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


def _overlaps_target_role(term: str, target_roles: list[str]) -> bool:
    term_key = term.strip().lower()
    if not term_key:
        return True
    for role in target_roles:
        role_key = role.strip().lower()
        if role_key and (term_key == role_key or term_key in role_key or role_key in term_key):
            return True
    return False


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)
