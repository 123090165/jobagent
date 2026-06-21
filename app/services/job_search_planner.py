from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError
from app.services.search_signal_normalizer import build_bilingual_search_signals

GENERIC_SUPPORTING_SIGNAL_TERMS = {
    "api",
    "apis",
    "c",
    "c++",
    "docker",
    "excel",
    "fastapi",
    "git",
    "matlab",
    "numpy",
    "pandas",
    "python",
    "pytorch",
    "sql",
    "sqlite",
    "tensorflow",
}


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
    signals = build_bilingual_search_signals(
        confirmed_profile.target_roles,
        confirmed_profile.search_keywords,
        confirmed_profile.core_skills,
    )
    keywords = _dedupe(
        _query_signal_seed(signals, confirmed_profile.search_keywords, confirmed_profile.core_skills)
    )
    provider_terms = _provider_query_signal_seed(
        signals,
        target_roles=target_roles,
        search_keywords=confirmed_profile.search_keywords,
        core_skills=confirmed_profile.core_skills,
    )
    locations = _dedupe(confirmed_profile.preferred_locations)
    queries = build_focused_provider_queries(target_roles, provider_terms)

    if not queries:
        queries.append("Software Engineer")

    warnings: list[str] = []
    if not confirmed_profile.preferred_locations:
        warnings.append("No preferred locations found; search will include remote-friendly defaults.")
    if not confirmed_profile.search_keywords:
        warnings.append("Search keywords were sparse; core skills were used to build the plan.")
    if signals["zh_terms"] and signals["en_terms"]:
        warnings.append(
            "Bilingual search signals were prepared for future English providers; CUHKSZ planning still prioritizes Chinese terms and common acronyms."
        )

    return JobSearchPlan(
        queries=_dedupe(queries),
        locations=locations,
        target_roles=target_roles,
        must_have_signals=_dedupe(signals["normalized_signals"])[:10],
        avoid_signals=_dedupe(confirmed_profile.risks)[:5],
        ranking_policy=(
            "Prefer target role overlap, skill overlap, and clear source metadata. "
            "Future English providers should use expanded English aliases from normalized search signals."
        ),
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
            and not _is_generic_supporting_signal(term)
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


def _query_signal_seed(
    signals: dict[str, object],
    search_keywords: list[str],
    core_skills: list[str],
) -> list[str]:
    zh_terms = [str(value) for value in signals.get("zh_terms", [])]
    en_terms = [str(value) for value in signals.get("en_terms", [])]
    acronyms = [term for term in en_terms if _looks_like_acronym(term)]
    english_fallback = [term for term in en_terms if not _looks_like_acronym(term)]
    return _dedupe(zh_terms + acronyms + search_keywords + core_skills + english_fallback)


def _provider_query_signal_seed(
    signals: dict[str, object],
    *,
    target_roles: list[str],
    search_keywords: list[str],
    core_skills: list[str],
) -> list[str]:
    zh_terms = [str(value) for value in signals.get("zh_terms", [])]
    en_terms = [str(value) for value in signals.get("en_terms", [])]
    acronyms = [term for term in en_terms if _looks_like_acronym(term)]
    english_fallback = [term for term in en_terms if not _looks_like_acronym(term)]
    candidates = _dedupe(
        zh_terms[:1]
        + acronyms
        + zh_terms[1:]
        + search_keywords
        + core_skills
        + english_fallback
    )
    focused = [
        term
        for term in candidates
        if not _overlaps_target_role(term, target_roles)
        and not _is_generic_supporting_signal(term)
    ]
    if focused:
        return _dedupe(focused)
    return _dedupe([term for term in candidates if not _overlaps_target_role(term, target_roles)])


def _overlaps_target_role(term: str, target_roles: list[str]) -> bool:
    term_key = term.strip().lower()
    if not term_key:
        return True
    for role in target_roles:
        role_key = role.strip().lower()
        if role_key and (term_key == role_key or term_key in role_key or role_key in term_key):
            return True
    return False


def _is_generic_supporting_signal(term: str) -> bool:
    normalized = term.strip().lower()
    return normalized in GENERIC_SUPPORTING_SIGNAL_TERMS


def _looks_like_acronym(value: str) -> bool:
    stripped = value.strip()
    return 2 <= len(stripped) <= 8 and stripped.upper() == stripped and any(char.isalpha() for char in stripped)
