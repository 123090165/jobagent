from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.job_search_planner import (
    JobSearchPlan,
    SearchConstraint,
    build_structured_constraints,
)
from app.services.job_search_providers.base import RawJobCandidate

LOCATION_ALIASES = {
    "shenzhen": ["shenzhen", "深圳", "深圳市"],
    "china": ["china", "中国"],
    "beijing": ["beijing", "北京", "北京市"],
    "shanghai": ["shanghai", "上海", "上海市"],
    "guangzhou": ["guangzhou", "广州", "广州市"],
    "hangzhou": ["hangzhou", "杭州", "杭州市"],
}

HardFilterStatus = Literal["accepted", "rejected", "unknown"]
HardFilterRejectionCode = Literal[
    "excluded_role",
    "seniority_mismatch",
    "work_type_mismatch",
    "location_mismatch",
    "stale_listing",
]


@dataclass(frozen=True)
class HardFilterDecision:
    candidate_index: int
    status: HardFilterStatus
    rejection_code: HardFilterRejectionCode | None = None
    evidence: str | None = None
    unknown_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class _HardFilterPolicy:
    excluded_roles: tuple[str, ...]
    reject_senior: bool
    required_employment_types: tuple[str, ...]
    constrained_locations: tuple[str, ...]
    required_work_arrangements: tuple[str, ...]


def evaluate_constraints(
    search_plan: JobSearchPlan,
    candidates: list[RawJobCandidate],
) -> list[HardFilterDecision]:
    policy = _build_hard_filter_policy(search_plan)
    return [
        _hard_filter_candidate(index, candidate, policy)
        for index, candidate in enumerate(candidates)
    ]


def candidate_text(candidate: RawJobCandidate) -> str:
    return " ".join(
        filter(
            None,
            [
                candidate.title or "",
                candidate.company or "",
                candidate.location or "",
                candidate.snippet or "",
                candidate.raw_description or "",
                " ".join(candidate.provider_warnings),
            ],
        )
    ).lower()


def location_matches(candidate_location: str, preferred_location: str) -> bool:
    if not candidate_location or not preferred_location:
        return False
    if preferred_location in candidate_location or candidate_location in preferred_location:
        return True
    for aliases in LOCATION_ALIASES.values():
        alias_values = [alias.lower() for alias in aliases]
        if any(alias in candidate_location for alias in alias_values) and any(
            alias in preferred_location for alias in alias_values
        ):
            return True
    return False


def _build_hard_filter_policy(search_plan: JobSearchPlan) -> _HardFilterPolicy:
    constraints = search_plan.structured_constraints or _legacy_structured_constraints(search_plan)
    return _HardFilterPolicy(
        excluded_roles=tuple(
            value
            for constraint in constraints
            if constraint.kind == "role_exclusion" and constraint.operator == "excluded"
            for value in constraint.values
        ),
        reject_senior=_excludes(constraints, "seniority", "senior"),
        required_employment_types=_required_values(constraints, "employment_type"),
        constrained_locations=tuple(
            value.lower()
            for constraint in constraints
            if constraint.kind == "location" and constraint.operator == "required"
            for value in constraint.values
        ),
        required_work_arrangements=_required_values(constraints, "work_arrangement"),
    )


def _legacy_structured_constraints(search_plan: JobSearchPlan) -> list[SearchConstraint]:
    """Keep older stored runs working while new runs use typed mission constraints."""
    return build_structured_constraints(
        search_plan.hard_constraints,
        search_plan.excluded_roles,
        [
            location
            for location in search_plan.locations
            if any(
                location_matches(constraint.lower(), location.lower())
                for constraint in search_plan.hard_constraints
            )
        ],
        search_plan.target_roles,
    )


def _required_values(constraints: list[SearchConstraint], kind: str) -> tuple[str, ...]:
    return tuple(
        value.casefold()
        for constraint in constraints
        if constraint.kind == kind and constraint.operator == "required"
        for value in constraint.values
    )


def _excludes(constraints: list[SearchConstraint], kind: str, value: str) -> bool:
    return any(
        constraint.kind == kind
        and constraint.operator == "excluded"
        and value in {item.casefold() for item in constraint.values}
        for constraint in constraints
    )


def _hard_filter_candidate(
    candidate_index: int,
    candidate: RawJobCandidate,
    policy: _HardFilterPolicy,
) -> HardFilterDecision:
    title = (candidate.title or "").strip()
    title_key = title.lower()
    text = candidate_text(candidate)
    unknown_fields: list[str] = []

    if any(_title_contains_term(title_key, role) for role in policy.excluded_roles):
        return _hard_rejection(candidate_index, "excluded_role", title)
    if not title and policy.excluded_roles:
        unknown_fields.append("role")

    is_senior = _contains_any(
        title_key,
        (
            "senior",
            "staff",
            "principal",
            "lead",
            "manager",
            "director",
            "资深",
            "高级",
            "负责人",
            "经理",
            "总监",
        ),
    )
    requires_internship = "internship" in policy.required_employment_types
    if is_senior and (policy.reject_senior or requires_internship):
        return _hard_rejection(candidate_index, "seniority_mismatch", title)
    if not title and (policy.reject_senior or requires_internship):
        unknown_fields.append("seniority")

    candidate_employment_types = _candidate_employment_types(text)
    if policy.required_employment_types:
        if candidate_employment_types and candidate_employment_types.isdisjoint(
            policy.required_employment_types
        ):
            return _hard_rejection(
                candidate_index,
                "work_type_mismatch",
                "Candidate employment type: " + ", ".join(sorted(candidate_employment_types)),
            )
        if not candidate_employment_types:
            unknown_fields.append("employment_type")

    candidate_location = (candidate.location or "").lower()
    if candidate_location and policy.constrained_locations and not any(
        location_matches(candidate_location, location)
        for location in policy.constrained_locations
    ):
        return _hard_rejection(candidate_index, "location_mismatch", candidate.location)
    if not candidate_location and policy.constrained_locations:
        unknown_fields.append("location")

    candidate_work_arrangements = _candidate_work_arrangements(text)
    if policy.required_work_arrangements:
        if candidate_work_arrangements and candidate_work_arrangements.isdisjoint(
            policy.required_work_arrangements
        ):
            return _hard_rejection(
                candidate_index,
                "work_type_mismatch",
                "Candidate work arrangement: "
                + ", ".join(sorted(candidate_work_arrangements)),
            )
        if not candidate_work_arrangements:
            unknown_fields.append("work_arrangement")

    if _contains_any(
        text,
        (
            "job expired",
            "listing expired",
            "position closed",
            "no longer accepting",
            "职位已过期",
            "停止招聘",
        ),
    ):
        return _hard_rejection(
            candidate_index,
            "stale_listing",
            "Listing explicitly indicates that it is closed or expired.",
        )

    return HardFilterDecision(
        candidate_index=candidate_index,
        status="unknown" if unknown_fields else "accepted",
        unknown_fields=tuple(dict.fromkeys(unknown_fields)),
    )


def _hard_rejection(
    candidate_index: int,
    rejection_code: HardFilterRejectionCode,
    evidence: str | None,
) -> HardFilterDecision:
    return HardFilterDecision(
        candidate_index=candidate_index,
        status="rejected",
        rejection_code=rejection_code,
        evidence=evidence,
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _candidate_employment_types(text: str) -> set[str]:
    types: set[str] = set()
    if _contains_any(text, ("intern", "internship", "实习")):
        types.add("internship")
    if _contains_any(text, ("full-time", "full time", "permanent role", "全职", "正式员工")):
        types.add("full_time")
    if _contains_any(text, ("part-time", "part time", "兼职")):
        types.add("part_time")
    if _contains_any(text, ("contract role", "contract position", "合同制")):
        types.add("contract")
    return types


def _candidate_work_arrangements(text: str) -> set[str]:
    arrangements: set[str] = set()
    if _contains_any(text, ("remote", "远程")):
        arrangements.add("remote")
    if _contains_any(text, ("onsite", "on-site", "daily office", "现场办公", "坐班")):
        arrangements.add("onsite")
    if _contains_any(text, ("hybrid", "混合办公")):
        arrangements.add("hybrid")
    return arrangements


def _title_contains_term(title: str, term: str) -> bool:
    normalized = term.strip().lower()
    if not title or not normalized:
        return False
    if normalized.isascii() and normalized.replace(" ", "").isalnum():
        return normalized in title.split() if " " not in normalized else normalized in title
    return normalized in title
