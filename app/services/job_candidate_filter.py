from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError


class CandidateFilterResult(BaseModel):
    selected_candidates: list[RawJobCandidate] = Field(default_factory=list)
    selected_indexes: list[int] = Field(default_factory=list)
    mode: Literal["deterministic", "llm", "fallback"]
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)


def filter_candidates(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    candidates: list[RawJobCandidate],
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None = None,
    limit: int | None = None,
) -> CandidateFilterResult:
    deterministic = _deterministic_filter(confirmed_profile, search_plan, candidates, limit=limit)
    if not use_llm:
        return deterministic

    if llm_service is None:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": "llm_service_unavailable",
                "quality_warnings": deterministic.quality_warnings + ["LLM filtering unavailable. Used deterministic ranking."],
            }
        )

    try:
        payload = llm_service.chat_completion_json(
            system_prompt=(
                "You rank existing job candidates only. "
                "Do not invent candidates or fields. "
                "Return JSON with selected_indexes and quality_warnings. "
                "selected_indexes must reference the provided candidate indexes only."
            ),
            user_prompt=(
                "Confirmed profile JSON:\n"
                f"{json.dumps(confirmed_profile.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                "Search plan JSON:\n"
                f"{search_plan.model_dump_json()}\n\n"
                "Candidates JSON:\n"
                f"{json.dumps([{**candidate.model_dump(mode='json'), 'index': index} for index, candidate in enumerate(candidates)], ensure_ascii=False)}"
            ),
        )
        raw_indexes = payload.get("selected_indexes", [])
        if not isinstance(raw_indexes, list):
            raise ValueError("selected_indexes must be a list")
        valid_indexes: list[int] = []
        for item in raw_indexes:
            index = int(item)
            if 0 <= index < len(candidates) and index not in valid_indexes:
                valid_indexes.append(index)
        if limit is not None:
            valid_indexes = valid_indexes[:limit]
        if not valid_indexes:
            raise ValueError("LLM did not select any valid candidates")
        return CandidateFilterResult(
            selected_candidates=[candidates[index] for index in valid_indexes],
            selected_indexes=valid_indexes,
            mode="llm",
            fallback_reason=None,
            quality_warnings=_dedupe_list(payload.get("quality_warnings", [])),
        )
    except (LLMServiceError, TypeError, ValueError) as exc:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": type(exc).__name__,
                "quality_warnings": deterministic.quality_warnings + [f"LLM filtering fallback triggered: {type(exc).__name__}."],
            }
        )


def _deterministic_filter(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    candidates: list[RawJobCandidate],
    *,
    limit: int | None = None,
) -> CandidateFilterResult:
    signals = _dedupe_list(
        confirmed_profile.target_roles
        + confirmed_profile.search_keywords
        + confirmed_profile.core_skills
        + search_plan.must_have_signals
    )
    avoid_signals = [item.lower() for item in search_plan.avoid_signals]
    scored: list[tuple[int, int]] = []
    for index, candidate in enumerate(candidates):
        text = " ".join(
            filter(
                None,
                [
                    candidate.title or "",
                    candidate.company or "",
                    candidate.location or "",
                    candidate.snippet or "",
                    candidate.raw_description or "",
                ],
            )
        ).lower()
        overlap = sum(1 for signal in signals if signal.lower() in text)
        penalty = sum(1 for signal in avoid_signals if signal and signal in text)
        scored.append((index, overlap * 10 - penalty * 3))
    scored.sort(key=lambda item: item[1], reverse=True)
    ranked_indexes = [index for index, _score in scored]
    if limit is not None:
        ranked_indexes = ranked_indexes[:limit]

    warnings: list[str] = []
    if not signals:
        warnings.append("Candidate ranking used limited profile signals.")
    return CandidateFilterResult(
        selected_candidates=[candidates[index] for index in ranked_indexes],
        selected_indexes=ranked_indexes,
        mode="deterministic",
        fallback_reason=None,
        quality_warnings=warnings,
    )


def _dedupe_list(values: list[str] | object) -> list[str]:
    if not isinstance(values, list):
        return []
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
