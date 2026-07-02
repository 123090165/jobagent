from __future__ import annotations

import json
from collections.abc import Iterable

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import JobSearchIntent
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError

GENERIC_TOOL_TERMS = {
    "api",
    "apis",
    "c",
    "c++",
    "docker",
    "excel",
    "fastapi",
    "figma",
    "git",
    "java",
    "javascript",
    "matlab",
    "numpy",
    "pandas",
    "powerpoint",
    "python",
    "pytorch",
    "react",
    "sql",
    "sqlite",
    "tableau",
    "tensorflow",
    "typescript",
    "vue",
}

ROLE_FAMILY_HINTS = {
    "engineering": ["engineer", "developer", "backend", "frontend", "software", "platform", "devops"],
    "data": ["data", "analytics", "analyst", "business intelligence", "bi"],
    "finance": ["finance", "financial", "investment", "risk", "quant", "accounting", "audit", "banking"],
    "product": ["product manager", "product operations", "product"],
    "marketing": ["marketing", "growth", "brand", "content", "social media"],
    "operations": ["operations", "ops", "supply chain", "customer success"],
    "design": ["design", "designer", "ux", "ui"],
    "research": ["research", "scientist", "lab"],
    "consulting": ["consulting", "consultant", "strategy"],
    "legal": ["legal", "compliance", "law"],
    "hr": ["human resources", "recruiting", "talent"],
}

INTENT_SYSTEM_PROMPT = """
You extract generic job-search intent from one confirmed profile.

Rules:
- Use only the confirmed profile. Do not invent industries, employers, credentials, job families, or skills.
- The output must work for any field: finance, marketing, operations, engineering, research, design, legal, HR, consulting, and others.
- Do not hard-code or prefer any example industry. The current profile decides the domain.
- Separate role titles, industry/domain words, evidence skills, generic tools, constraints, and negative signals.
- Generic tools are broad tools or programming/productivity tools. They can help search, but should not define the domain by themselves.
- broad_queries should be short role/category searches.
- domain_queries should combine a role or role family with domain words.
- evidence_queries should combine a role/domain with distinctive evidence skills.
- tool_queries should be lowest priority and use only when they add useful recall.
- Return deterministic JSON only.

Return this JSON object:
{
  "role_titles": ["..."],
  "role_families": ["..."],
  "industry_domains": ["..."],
  "evidence_skills": ["..."],
  "generic_tools": ["..."],
  "constraints": ["..."],
  "negative_signals": ["..."],
  "broad_queries": ["..."],
  "domain_queries": ["..."],
  "evidence_queries": ["..."],
  "tool_queries": ["..."],
  "quality_warnings": ["..."]
}
""".strip()


def build_search_intent(
    confirmed_profile: ConfirmedProfile,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchIntent:
    deterministic = build_deterministic_search_intent(confirmed_profile)
    if not use_llm:
        return deterministic

    if llm_service is None:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": "llm_service_unavailable",
                "quality_warnings": _dedupe(
                    deterministic.quality_warnings
                    + ["LLM intent extraction unavailable. Used deterministic intent."]
                ),
            }
        )

    try:
        payload = llm_service.chat_completion_json(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=(
                "Confirmed profile JSON:\n"
                f"{json.dumps(confirmed_profile.model_dump(mode='json'), ensure_ascii=False)}"
            ),
        )
        intent = JobSearchIntent.model_validate(
            {
                "role_titles": payload.get("role_titles", []),
                "role_families": payload.get("role_families", []),
                "industry_domains": payload.get("industry_domains", []),
                "evidence_skills": payload.get("evidence_skills", []),
                "generic_tools": payload.get("generic_tools", []),
                "constraints": payload.get("constraints", []),
                "negative_signals": payload.get("negative_signals", []),
                "broad_queries": payload.get("broad_queries", []),
                "domain_queries": payload.get("domain_queries", []),
                "evidence_queries": payload.get("evidence_queries", []),
                "tool_queries": payload.get("tool_queries", []),
                "quality_warnings": payload.get("quality_warnings", []),
                "mode": "llm",
                "fallback_reason": None,
            }
        )
        return normalize_search_intent(intent, fallback=deterministic)
    except (LLMServiceError, ValueError, TypeError) as exc:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": type(exc).__name__,
                "quality_warnings": _dedupe(
                    deterministic.quality_warnings
                    + [f"LLM intent extraction fallback triggered: {type(exc).__name__}."]
                ),
            }
        )


def build_deterministic_search_intent(confirmed_profile: ConfirmedProfile) -> JobSearchIntent:
    role_titles = _dedupe(confirmed_profile.target_roles)
    role_families = _infer_role_families(
        role_titles + confirmed_profile.target_directions + confirmed_profile.search_keywords
    )
    candidate_terms = _dedupe(
        confirmed_profile.search_keywords
        + confirmed_profile.target_directions
        + confirmed_profile.core_skills
        + confirmed_profile.supporting_skills
    )
    generic_tools = [term for term in candidate_terms if is_generic_tool_term(term)]
    evidence_skills = [
        term
        for term in candidate_terms
        if term not in generic_tools and not _overlaps_any(term, role_titles)
    ]
    industry_domains = [
        term
        for term in _dedupe(confirmed_profile.target_directions + confirmed_profile.search_keywords)
        if term not in generic_tools and not _overlaps_any(term, role_titles)
    ]
    constraints = _dedupe(confirmed_profile.preferred_locations + confirmed_profile.work_arrangements)
    negative_signals = _dedupe(confirmed_profile.risks)
    intent = JobSearchIntent(
        role_titles=role_titles,
        role_families=role_families,
        industry_domains=industry_domains[:8],
        evidence_skills=evidence_skills[:10],
        generic_tools=generic_tools[:8],
        constraints=constraints[:8],
        negative_signals=negative_signals[:8],
        mode="deterministic",
        fallback_reason=None,
        quality_warnings=[],
    )
    return normalize_search_intent(intent, fallback=None)


def normalize_search_intent(
    intent: JobSearchIntent,
    *,
    fallback: JobSearchIntent | None,
) -> JobSearchIntent:
    role_titles = _dedupe(intent.role_titles) or (fallback.role_titles if fallback else [])
    role_families = _dedupe(intent.role_families) or (fallback.role_families if fallback else [])
    generic_tools = _dedupe(intent.generic_tools) or (fallback.generic_tools if fallback else [])
    evidence_skills = [
        term
        for term in (_dedupe(intent.evidence_skills) or (fallback.evidence_skills if fallback else []))
        if term not in generic_tools and not _overlaps_any(term, role_titles)
    ]
    industry_domains = [
        term
        for term in (_dedupe(intent.industry_domains) or (fallback.industry_domains if fallback else []))
        if term not in generic_tools and not _overlaps_any(term, role_titles)
    ]
    constraints = _dedupe(intent.constraints) or (fallback.constraints if fallback else [])
    negative_signals = _dedupe(intent.negative_signals) or (fallback.negative_signals if fallback else [])
    broad_queries = _dedupe(intent.broad_queries) or _build_broad_queries(role_titles, role_families)
    domain_queries = _dedupe(intent.domain_queries) or _build_domain_queries(role_titles, role_families, industry_domains)
    evidence_queries = _dedupe(intent.evidence_queries) or _build_evidence_queries(
        role_titles,
        industry_domains,
        evidence_skills,
    )
    tool_queries = _dedupe(intent.tool_queries) or _build_tool_queries(role_titles, generic_tools)
    warnings = _dedupe(intent.quality_warnings)
    if not role_titles and not role_families:
        warnings.append("Search intent has sparse role signals; queries use available skills and domains.")
    return intent.model_copy(
        update={
            "role_titles": role_titles[:6],
            "role_families": role_families[:6],
            "industry_domains": industry_domains[:8],
            "evidence_skills": evidence_skills[:10],
            "generic_tools": generic_tools[:8],
            "constraints": constraints[:8],
            "negative_signals": negative_signals[:8],
            "broad_queries": broad_queries[:6],
            "domain_queries": domain_queries[:8],
            "evidence_queries": evidence_queries[:8],
            "tool_queries": tool_queries[:6],
            "quality_warnings": warnings,
        }
    )


def build_queries_from_intent(intent: JobSearchIntent) -> list[str]:
    return _dedupe(
        intent.broad_queries
        + intent.domain_queries
        + intent.evidence_queries
        + intent.tool_queries
    )


def is_generic_tool_term(term: str) -> bool:
    normalized = _normalize_key(term)
    return normalized in GENERIC_TOOL_TERMS


def _build_broad_queries(role_titles: list[str], role_families: list[str]) -> list[str]:
    return _dedupe(role_titles[:4] + role_families[:2])


def _build_domain_queries(
    role_titles: list[str],
    role_families: list[str],
    industry_domains: list[str],
) -> list[str]:
    anchors = role_titles[:3] or role_families[:2]
    queries = []
    for anchor in anchors:
        for domain in industry_domains[:3]:
            if not _overlaps_any(domain, [anchor]):
                queries.append(f"{anchor} {domain}".strip())
    return _dedupe(queries)


def _build_evidence_queries(
    role_titles: list[str],
    industry_domains: list[str],
    evidence_skills: list[str],
) -> list[str]:
    anchors = role_titles[:3] or industry_domains[:2]
    evidence_seed = evidence_skills[:4]
    queries = []
    for anchor in anchors:
        focused = [term for term in evidence_seed if not _overlaps_any(term, [anchor])]
        if focused:
            queries.append(f"{anchor} {' '.join(focused[:2])}".strip())
    return _dedupe(queries)


def _build_tool_queries(role_titles: list[str], generic_tools: list[str]) -> list[str]:
    if not role_titles or not generic_tools:
        return []
    return [f"{role_titles[0]} {' '.join(generic_tools[:2])}".strip()]


def _infer_role_families(terms: list[str]) -> list[str]:
    families: list[str] = []
    normalized_terms = [_normalize_key(term) for term in terms]
    for family, hints in ROLE_FAMILY_HINTS.items():
        if any(hint in term for term in normalized_terms for hint in hints):
            families.append(family)
    return families


def _overlaps_any(term: str, values: list[str]) -> bool:
    term_key = _normalize_key(term)
    if not term_key:
        return True
    for value in values:
        value_key = _normalize_key(value)
        if value_key and (term_key == value_key or term_key in value_key or value_key in term_key):
            return True
    return False


def _normalize_key(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _dedupe(values: Iterable[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = _normalize_key(text)
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items
