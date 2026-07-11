from __future__ import annotations

import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from app.agents.jd_analysis_agent import run_jd_analysis_agent
from app.services.job_candidate_filter import CandidateFilterResult, CandidateScorecard
from app.services.job_search_providers.base import RawJobCandidate
from app.services.llm_provider import JSONChatLLM

DEFAULT_JD_ANALYSIS_CONCURRENCY = 3
MAX_JD_ANALYSIS_CONCURRENCY = 8


def _analyze_candidates(
    filtered: CandidateFilterResult,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None,
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    mode_counter: Counter[str] = Counter()
    guardrails: list[str] = []
    quality_warnings: list[str] = []
    fallback_reason: str | None = None
    scorecards_by_index = {scorecard.candidate_index: scorecard for scorecard in filtered.scorecards}
    selected = list(zip(filtered.selected_indexes, filtered.selected_candidates))
    concurrency = _jd_analysis_concurrency(use_llm=use_llm, candidate_count=len(selected))
    if concurrency <= 1:
        analyzed_records = [
            _analyze_candidate_for_job_search(
                candidate_index,
                candidate,
                use_llm=use_llm,
                llm_service=llm_service,
                scorecard=scorecards_by_index.get(candidate_index),
            )
            for candidate_index, candidate in selected
        ]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            analyzed_records = list(
                executor.map(
                    lambda item: _analyze_candidate_for_job_search(
                        item[0],
                        item[1],
                        use_llm=use_llm,
                        llm_service=llm_service,
                        scorecard=scorecards_by_index.get(item[0]),
                    ),
                    selected,
                )
            )

    fallback_count = 0
    candidate_runs: list[dict[str, object]] = []
    fallback_reasons: Counter[str] = Counter()
    for record in analyzed_records:
        metadata = record["metadata"]
        mode_counter[metadata.mode] += 1
        if metadata.mode == "fallback" or metadata.fallback_reason:
            fallback_count += 1
            fallback_reasons[metadata.fallback_reason or "fallback"] += 1
        if metadata.fallback_reason and fallback_reason is None:
            fallback_reason = metadata.fallback_reason
        for item in metadata.guardrails:
            if item not in guardrails:
                guardrails.append(item)
        for item in metadata.quality_warnings:
            if item not in quality_warnings:
                quality_warnings.append(item)
        items.append(record["item"])
        candidate_runs.append(record["run_diagnostics"])
    return {
        "items": items,
        "mode": _summarize_analysis_mode(mode_counter),
        "fallback_reason": fallback_reason,
        "guardrails": guardrails,
        "quality_warnings": quality_warnings + filtered.quality_warnings,
        "concurrency": concurrency,
        "fallback_count": fallback_count,
        "mode_counts": dict(mode_counter),
        "timings_ms": _summarize_candidate_timings(candidate_runs),
        "candidate_runs": candidate_runs,
        "fallback_reasons": dict(fallback_reasons),
    }


def _analyze_candidate_for_job_search(
    candidate_index: int,
    candidate: RawJobCandidate,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None,
    scorecard: CandidateScorecard | None,
) -> dict[str, object]:
    text = (candidate.raw_description or candidate.snippet or candidate.title or "No job description provided.").strip()
    start = time.perf_counter()
    try:
        result = run_jd_analysis_agent(
            text,
            use_llm=use_llm,
            service=llm_service,  # type: ignore[arg-type]
        )
    except Exception as exc:
        result = run_jd_analysis_agent(text, use_llm=False)
        result = type(result)(
            output=result.output,
            metadata=result.metadata.model_copy(
                update={
                    "mode": "fallback",
                    "fallback_reason": type(exc).__name__,
                    "quality_warnings": [
                        f"JD analysis fallback triggered: {type(exc).__name__}."
                    ],
                }
            ),
        )
    duration_ms = _elapsed_ms(start)
    fallback_warnings = result.metadata.quality_warnings[:3] if result.metadata.fallback_reason else []
    return {
        "metadata": result.metadata,
        "run_diagnostics": {
            "candidate_index": candidate_index,
            "title": _truncate_detail_text(candidate.title, 80),
            "source_provider": candidate.source_provider,
            "mode": result.metadata.mode,
            "fallback_reason": result.metadata.fallback_reason,
            "duration_ms": duration_ms,
            "jd_text_chars": len(text),
            "quality_warning_count": len(result.metadata.quality_warnings),
            "fallback_warnings": fallback_warnings,
        },
        "item": {
            "candidate": candidate,
            "analysis": result.output,
            "analysis_mode": result.metadata.mode,
            "scorecard": scorecard,
        },
    }


def _jd_analysis_concurrency(*, use_llm: bool, candidate_count: int) -> int:
    if not use_llm or candidate_count <= 1:
        return 1
    raw_value = os.getenv("JOBAGENT_JD_ANALYSIS_CONCURRENCY")
    try:
        configured = int(raw_value) if raw_value else DEFAULT_JD_ANALYSIS_CONCURRENCY
    except ValueError:
        configured = DEFAULT_JD_ANALYSIS_CONCURRENCY
    capped = min(configured, MAX_JD_ANALYSIS_CONCURRENCY, candidate_count)
    return max(1, capped)


def _summarize_candidate_timings(candidate_runs: list[dict[str, object]]) -> dict[str, float]:
    durations = [
        float(item["duration_ms"])
        for item in candidate_runs
        if isinstance(item.get("duration_ms"), int | float)
    ]
    if not durations:
        return {
            "total_candidate_work": 0.0,
            "min_candidate": 0.0,
            "max_candidate": 0.0,
            "average_candidate": 0.0,
        }
    return {
        "total_candidate_work": round(sum(durations), 3),
        "min_candidate": round(min(durations), 3),
        "max_candidate": round(max(durations), 3),
        "average_candidate": round(sum(durations) / len(durations), 3),
    }


def _truncate_detail_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1] + "..."


def _summarize_analysis_mode(mode_counter: Counter[str]) -> str:
    if not mode_counter:
        return "mock"
    if mode_counter.get("fallback"):
        return "fallback"
    if mode_counter.get("llm"):
        return "llm"
    return "mock"


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)
