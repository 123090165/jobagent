"""把结构化搜索意图转成 Provider 查询、硬约束和排序信号。"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import JobSearchIntent, PlannedQuery
from app.services.job_search_intent import (
    build_queries_from_intent,
    build_search_intent,
    is_generic_tool_term,
)
from app.services.llm_provider import JSONChatLLM

WORK_ARRANGEMENT_BY_ALIAS = {
    "remote": "remote",
    "remote only": "remote",
    "远程": "remote",
    "仅远程": "remote",
    "onsite": "onsite",
    "on-site": "onsite",
    "现场办公": "onsite",
    "hybrid": "hybrid",
    "混合办公": "hybrid",
}
EMPLOYMENT_TYPE_BY_ALIAS = {
    "intern": "internship",
    "internship": "internship",
    "实习": "internship",
    "实习生": "internship",
    "full-time": "full_time",
    "full time": "full_time",
    "全职": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "兼职": "part_time",
    "contract": "contract",
    "合同制": "contract",
}


class SearchConstraint(BaseModel):
    """表示一个可用于 Provider 查询或候选过滤的结构化约束。"""
    kind: Literal[
        "location",
        "work_arrangement",
        "employment_type",
        "seniority",
        "role_exclusion",
    ]
    operator: Literal["required", "excluded"]
    values: list[str] = Field(default_factory=list)
    source_text: str


class JobSearchPlan(BaseModel):
    """冻结一次搜索使用的查询、角色、地点、约束和排序信号。"""
    planned_queries: list[PlannedQuery] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    must_have_signals: list[str] = Field(default_factory=list)
    avoid_signals: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    structured_constraints: list[SearchConstraint] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)
    ranking_policy: str
    search_intent: JobSearchIntent | None = None
    mode: Literal["deterministic", "llm", "fallback"]
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, object] = Field(default_factory=dict)

    @property
    def queries(self) -> list[str]:
        """Compatibility view for call sites that only need query text."""
        return [item.query for item in self.planned_queries]


def build_search_plan(
    confirmed_profile: ConfirmedProfile,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchPlan:
    """把 confirmed profile、mission 和请求覆盖项合并成稳定搜索计划。"""
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


def build_structured_constraints(
    mission_constraints: list[str],
    excluded_roles: list[str],
    known_locations: list[str],
    target_roles: list[str] | None = None,
) -> list[SearchConstraint]:
    """把地点、排除岗位和 must-have 文本转换为可解释约束。"""
    constraints: list[SearchConstraint] = []
    locations_by_key = {item.casefold(): item for item in known_locations}
    for source_text in mission_constraints:
        key = source_text.strip().casefold()
        work_arrangement = WORK_ARRANGEMENT_BY_ALIAS.get(key)
        employment_type = EMPLOYMENT_TYPE_BY_ALIAS.get(key)
        if key in locations_by_key:
            constraints.append(SearchConstraint(
                kind="location",
                operator="required",
                values=[locations_by_key[key]],
                source_text=source_text,
            ))
        elif work_arrangement:
            constraints.append(SearchConstraint(
                kind="work_arrangement",
                operator="required",
                values=[work_arrangement],
                source_text=source_text,
            ))
        elif employment_type or any(
            term in key
            for term in (
                "internship only",
                "intern only",
                "only internship",
                "只要实习",
                "仅限实习",
                "必须是实习",
                "只考虑实习",
            )
        ):
            constraints.append(SearchConstraint(
                kind="employment_type",
                operator="required",
                values=[employment_type or "internship"],
                source_text=source_text,
            ))
        elif any(
            term in key
            for term in ("no senior", "exclude senior", "不要高级", "不要资深", "只要初级")
        ):
            constraints.append(SearchConstraint(
                kind="seniority",
                operator="excluded",
                values=["senior"],
                source_text=source_text,
            ))
    constraints.extend(
        SearchConstraint(
            kind="role_exclusion",
            operator="excluded",
            values=[role],
            source_text=role,
        )
        for role in excluded_roles
    )
    if not any(constraint.kind == "employment_type" for constraint in constraints):
        intern_role = next(
            (role for role in target_roles or [] if _is_intern_role(role)),
            None,
        )
        if intern_role:
            constraints.append(SearchConstraint(
                kind="employment_type",
                operator="required",
                values=["internship"],
                source_text=intern_role,
            ))
    return constraints


def _is_intern_role(role: str) -> bool:
    key = role.casefold()
    tokens = key.replace("/", " ").replace("-", " ").split()
    return "实习" in key or "intern" in tokens or "internship" in tokens


def _build_plan_from_intent(
    confirmed_profile: ConfirmedProfile,
    intent: JobSearchIntent,
) -> JobSearchPlan:
    target_roles = _dedupe(intent.role_titles or confirmed_profile.target_roles)
    locations = _dedupe(confirmed_profile.preferred_locations)
    queries = build_queries_from_intent(intent)
    planned_queries = _build_typed_queries(intent, queries)

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
        planned_queries.append(
            PlannedQuery(
                query=queries[-1],
                query_type="fallback",
                priority=0.4,
                rationale="No stronger role, domain, or evidence query was available.",
            )
        )

    warnings: list[str] = []
    if not confirmed_profile.preferred_locations:
        warnings.append("No preferred locations found; search will include remote-friendly defaults.")
    if not confirmed_profile.search_keywords and not intent.industry_domains and not intent.evidence_skills:
        warnings.append("Search keywords were sparse; core skills were used to build the plan.")
    warnings = _dedupe(warnings + intent.quality_warnings)

    return JobSearchPlan(
        planned_queries=planned_queries,
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


def _build_typed_queries(
    intent: JobSearchIntent,
    executable_queries: list[str],
) -> list[PlannedQuery]:
    executable = {query.strip().lower() for query in executable_queries}
    groups = (
        (intent.broad_queries, "broad", 0.82, "Short role query for broad recall."),
        (intent.domain_queries, "role_domain", 0.92, "Role and domain combination."),
        (intent.evidence_queries, "evidence", 0.88, "Role query anchored by distinctive evidence."),
        (intent.tool_queries, "tool", 0.55, "Tool-supported fallback recall."),
    )
    planned: list[PlannedQuery] = []
    seen: set[str] = set()
    for queries, query_type, priority, rationale in groups:
        for query in queries:
            text = query.strip()
            key = text.lower()
            if not text or key not in executable or key in seen:
                continue
            seen.add(key)
            planned.append(
                PlannedQuery(
                    query=text,
                    query_type=query_type,
                    priority=priority,
                    rationale=rationale,
                )
            )
    return planned


def build_focused_provider_queries(target_roles: list[str], search_signal_terms: list[str]) -> list[str]:
    """在查询预算内优先组合高信息量角色与证据词，减少泛化召回。"""
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
