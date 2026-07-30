"""串联硬约束、确定性打分和可选 LLM 重排，并保持失败时可用的本地结果。"""

from __future__ import annotations

from dataclasses import asdict
import time

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_candidate_constraints import (
    HardFilterDecision,
    HardFilterRejectionCode,
    HardFilterStatus,
    evaluate_constraints,
)
from app.services.job_candidate_reranker import (
    LLM_CANDIDATE_RANKING_SYSTEM_PROMPT,
    apply_mission_penalties,
    build_rerank_prompt,
    validate_llm_scorecards,
)
from app.services.job_candidate_scoring import (
    SCORE_BREAKDOWN_KEYS,
    CandidateConfidenceLabel,
    CandidateFilterResult,
    CandidateScorecard,
    build_candidate_scorecard,
    dedupe_list,
    deterministic_filter,
)
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError

__all__ = [
    "CandidateConfidenceLabel",
    "CandidateFilterResult",
    "CandidateScorecard",
    "HardFilterDecision",
    "HardFilterRejectionCode",
    "HardFilterStatus",
    "LLM_CANDIDATE_RANKING_SYSTEM_PROMPT",
    "SCORE_BREAKDOWN_KEYS",
    "build_candidate_scorecard",
    "filter_candidates",
]


def filter_candidates(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    candidates: list[RawJobCandidate],
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None = None,
    limit: int | None = None,
) -> CandidateFilterResult:
    total_start = time.perf_counter()
    deterministic_start = time.perf_counter()
    decisions = evaluate_constraints(search_plan, candidates)
    accepted_indexes = [
        decision.candidate_index
        for decision in decisions
        if decision.status != "rejected"
    ]
    deterministic = deterministic_filter(
        confirmed_profile,
        search_plan,
        candidates,
        limit=limit,
        allowed_indexes=set(accepted_indexes),
    )
    base_diagnostics = {
        "hard_filter": {
            "input_count": len(candidates),
            "accepted_count": sum(decision.status == "accepted" for decision in decisions),
            "unknown_count": sum(decision.status == "unknown" for decision in decisions),
            "eligible_count": len(accepted_indexes),
            "rejected_count": sum(decision.status == "rejected" for decision in decisions),
            "rejections": [
                asdict(decision) for decision in decisions if decision.status == "rejected"
            ],
            "unknowns": [
                asdict(decision) for decision in decisions if decision.status == "unknown"
            ],
        },
        "timings_ms": {
            "deterministic_ranking": _elapsed_ms(deterministic_start),
        },
        "payload_stats": {
            "candidate_count": len(candidates),
            "requested_limit": limit or len(candidates),
        },
    }
    if not accepted_indexes:
        return deterministic.model_copy(
            update={
                "quality_warnings": deterministic.quality_warnings
                + ["All recalled candidates were rejected by explicit hard constraints."],
                "diagnostics": _with_total_timing(base_diagnostics, total_start),
            }
        )
    if not use_llm:
        return deterministic.model_copy(
            update={
                "diagnostics": _with_total_timing(base_diagnostics, total_start),
            }
        )

    if llm_service is None:
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": "llm_service_unavailable",
                "quality_warnings": deterministic.quality_warnings
                + ["LLM filtering unavailable. Used deterministic ranking."],
                "diagnostics": _with_total_timing(
                    {
                        **base_diagnostics,
                        "fallback_diagnostics": {
                            "reason": "llm_service_unavailable",
                        },
                    },
                    total_start,
                ),
            }
        )

    pre_rank_limit = min(len(accepted_indexes), max(20, (limit or 10) * 3))
    if len(accepted_indexes) > pre_rank_limit:
        pre_ranked = deterministic_filter(
            confirmed_profile,
            search_plan,
            candidates,
            limit=pre_rank_limit,
            allowed_indexes=set(accepted_indexes),
        )
        llm_candidates = pre_ranked.selected_candidates
        original_indexes = pre_ranked.selected_indexes
    else:
        original_indexes = accepted_indexes
        llm_candidates = [candidates[index] for index in original_indexes]

    llm_timings: dict[str, float] = {}
    llm_payload_stats: dict[str, object] = {}
    request_start: float | None = None
    validation_start: float | None = None
    try:
        prompt_start = time.perf_counter()
        user_prompt, candidates_json = build_rerank_prompt(
            confirmed_profile,
            search_plan,
            llm_candidates,
            requested_limit=limit or len(candidates),
        )
        llm_timings["prompt_build"] = _elapsed_ms(prompt_start)
        llm_payload_stats.update(
            {
                "system_prompt_chars": len(LLM_CANDIDATE_RANKING_SYSTEM_PROMPT),
                "user_prompt_chars": len(user_prompt),
                "candidate_payload_chars": len(candidates_json),
            }
        )
        request_start = time.perf_counter()
        payload = llm_service.chat_completion_json(
            system_prompt=LLM_CANDIDATE_RANKING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        llm_timings["llm_request"] = _elapsed_ms(request_start)
        validation_start = time.perf_counter()
        scorecards = validate_llm_scorecards(
            payload,
            candidate_count=len(llm_candidates),
            limit=limit,
        )
        scorecards = [
            scorecard.model_copy(
                update={"candidate_index": original_indexes[scorecard.candidate_index]}
            )
            for scorecard in scorecards
        ]
        scorecards = apply_mission_penalties(
            scorecards,
            candidates,
            search_plan.avoid_signals,
        )
        llm_timings["response_validation"] = _elapsed_ms(validation_start)
        valid_indexes = [scorecard.candidate_index for scorecard in scorecards]
        if limit is not None:
            valid_indexes = valid_indexes[:limit]
        if not valid_indexes:
            raise ValueError("LLM did not select any valid candidates")
        quality_warnings = dedupe_list(payload.get("quality_warnings", []))
        return CandidateFilterResult(
            selected_candidates=[candidates[index] for index in valid_indexes],
            selected_indexes=valid_indexes,
            scorecards=scorecards[: len(valid_indexes)],
            mode="llm",
            fallback_reason=None,
            quality_warnings=quality_warnings,
            diagnostics=_with_total_timing(
                {
                    **base_diagnostics,
                    "timings_ms": {
                        **base_diagnostics["timings_ms"],
                        **llm_timings,
                    },
                    "payload_stats": {
                        **base_diagnostics["payload_stats"],
                        **llm_payload_stats,
                        "returned_scorecard_count": len(scorecards),
                        "pre_rank_candidate_count": len(llm_candidates),
                        "quality_warning_count": len(quality_warnings),
                    },
                },
                total_start,
            ),
        )
    except (LLMServiceError, TypeError, ValueError) as exc:
        if request_start is not None and "llm_request" not in llm_timings:
            llm_timings["llm_request"] = _elapsed_ms(request_start)
        if validation_start is not None and "response_validation" not in llm_timings:
            llm_timings["response_validation"] = _elapsed_ms(validation_start)
        return deterministic.model_copy(
            update={
                "mode": "fallback",
                "fallback_reason": type(exc).__name__,
                "quality_warnings": deterministic.quality_warnings
                + [f"LLM filtering fallback triggered: {type(exc).__name__}."],
                "diagnostics": _with_total_timing(
                    {
                        **base_diagnostics,
                        "timings_ms": {
                            **base_diagnostics["timings_ms"],
                            **llm_timings,
                        },
                        "payload_stats": {
                            **base_diagnostics["payload_stats"],
                            **llm_payload_stats,
                        },
                        "fallback_diagnostics": {
                            "reason": type(exc).__name__,
                        },
                    },
                    total_start,
                ),
            }
        )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def _with_total_timing(diagnostics: dict[str, object], start: float) -> dict[str, object]:
    timings = dict(diagnostics.get("timings_ms", {}))
    timings["total"] = _elapsed_ms(start)
    return {**diagnostics, "timings_ms": timings}
