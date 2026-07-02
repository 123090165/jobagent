from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError

CandidateConfidenceLabel = Literal["strong", "medium", "limited", "weak"]

SCORE_BREAKDOWN_KEYS = [
    "role_alignment",
    "domain_alignment",
    "skill_evidence",
    "seniority_and_work_type",
    "location_fit",
    "jd_evidence_quality",
    "risk_penalty",
]

LLM_CANDIDATE_RANKING_SYSTEM_PROMPT = """
You are ranking existing job candidates for one confirmed user profile.

Hard guardrails:
- Rank only the candidates in the input. Do not invent, merge, rewrite, or drop candidates because metadata is incomplete.
- Missing company, location, source_url, or sparse JD text is a confidence/risk issue, not an automatic rejection.
- Prefer role/domain evidence over generic tool overlap. Python, MATLAB, PyTorch, SQL, FastAPI, Docker, Git, and similar tool words are weak signals unless the role/domain also matches.
- Use only evidence visible in the candidate title, company, location, snippet, raw_description, provider_warnings, confirmed profile, and search plan.
- Make the same decision for the same input: use integer scores, no randomness, no prose outside JSON, and break exact score ties by lower candidate index.

Return only this JSON object:
{
  "ranked_candidates": [
    {
      "index": 0,
      "match_score": 0,
      "confidence_label": "strong|medium|limited|weak",
      "score_breakdown": {
        "role_alignment": 0,
        "domain_alignment": 0,
        "skill_evidence": 0,
        "seniority_and_work_type": 0,
        "location_fit": 0,
        "jd_evidence_quality": 0,
        "risk_penalty": 0
      },
      "matched_keywords": ["..."],
      "match_reasons": ["..."],
      "risks": ["..."],
      "evidence_quotes": ["..."]
    }
  ],
  "quality_warnings": ["..."]
}

Scoring rubric:
- role_alignment, 0-25: 25 exact target role or very close role; 18-24 adjacent role with the same function; 8-17 broad software/data/AI role; 0-7 unrelated or misleading title.
- domain_alignment, 0-25: 20-25 direct overlap with the profile's target_directions, search_keywords, domain words, and distinctive evidence signals; 10-19 adjacent domain/function overlap; 0-9 generic role/tool overlap without the profile's domain evidence.
- skill_evidence, 0-20: credit concrete required skills from the confirmed profile and JD. Give more weight to domain-specific skills and methods than generic tools. Do not over-score a role solely because it mentions Python/PyTorch/FastAPI/SQL.
- seniority_and_work_type, 0-10: 8-10 internship/new-grad/entry-level fit when the profile suggests that level; 4-7 ambiguous level; 0-3 senior-only, many years required, or mismatched employment type.
- location_fit, 0-10: 8-10 explicit preferred location/remote match; 4-7 location missing or nearby; 0-3 clear mismatch.
- jd_evidence_quality, 0-10: 8-10 has usable JD details and source URL; 4-7 sparse but enough title/snippet evidence; 0-3 title-only, broken source, or heavy provider warnings.
- risk_penalty, 0-30: subtract for clear mismatch, seniority gap, wrong domain, role-function drift away from the profile's stated direction, missing source details, or provider warnings.

Compute match_score = clamp(role_alignment + domain_alignment + skill_evidence + seniority_and_work_type + location_fit + jd_evidence_quality - risk_penalty, 0, 100).
Use confidence_label from match_score: strong 85-100, medium 72-84, limited 58-71, weak 0-57.
Return at most the requested limit, sorted by match_score descending, then role_alignment descending, domain_alignment descending, then candidate index ascending.
""".strip()


class CandidateScorecard(BaseModel):
    candidate_index: int
    match_score: int = Field(ge=0, le=100)
    confidence_label: CandidateConfidenceLabel
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    matched_keywords: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)


class CandidateFilterResult(BaseModel):
    selected_candidates: list[RawJobCandidate] = Field(default_factory=list)
    selected_indexes: list[int] = Field(default_factory=list)
    scorecards: list[CandidateScorecard] = Field(default_factory=list)
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
            system_prompt=LLM_CANDIDATE_RANKING_SYSTEM_PROMPT,
            user_prompt=(
                f"Requested result limit: {limit or len(candidates)}\n\n"
                "Confirmed profile JSON:\n"
                f"{json.dumps(confirmed_profile.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                "Search plan JSON:\n"
                f"{search_plan.model_dump_json()}\n\n"
                "Candidates JSON:\n"
                f"{json.dumps([{**candidate.model_dump(mode='json'), 'index': index} for index, candidate in enumerate(candidates)], ensure_ascii=False)}"
            ),
        )
        scorecards = _validate_llm_scorecards(payload, candidate_count=len(candidates), limit=limit)
        valid_indexes = [scorecard.candidate_index for scorecard in scorecards]
        if limit is not None:
            valid_indexes = valid_indexes[:limit]
        if not valid_indexes:
            raise ValueError("LLM did not select any valid candidates")
        return CandidateFilterResult(
            selected_candidates=[candidates[index] for index in valid_indexes],
            selected_indexes=valid_indexes,
            scorecards=scorecards[: len(valid_indexes)],
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
    scored: list[tuple[int, int, list[str]]] = []
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
        matched = [signal for signal in signals if signal.lower() in text]
        scored.append((index, overlap * 10 - penalty * 3, matched))
    scored.sort(key=lambda item: item[1], reverse=True)
    ranked_indexes = [index for index, _score, _matched in scored]
    if limit is not None:
        ranked_indexes = ranked_indexes[:limit]
    score_by_index = {index: score for index, score, _matched in scored}
    matched_by_index = {index: matched for index, _score, matched in scored}

    warnings: list[str] = []
    if not signals:
        warnings.append("Candidate ranking used limited profile signals.")
    return CandidateFilterResult(
        selected_candidates=[candidates[index] for index in ranked_indexes],
        selected_indexes=ranked_indexes,
        scorecards=[
            CandidateScorecard(
                candidate_index=index,
                match_score=max(0, min(100, 45 + score_by_index[index])),
                confidence_label=_confidence_label_for_score(max(0, min(100, 45 + score_by_index[index]))),
                score_breakdown={},
                matched_keywords=matched_by_index[index][:6],
                match_reasons=(
                    ["Matched profile/search-plan signals: " + ", ".join(matched_by_index[index][:5]) + "."]
                    if matched_by_index[index]
                    else ["Candidate remains in scope based on broad search-plan alignment."]
                ),
                risks=[],
                evidence_quotes=[],
            )
            for index in ranked_indexes
        ],
        mode="deterministic",
        fallback_reason=None,
        quality_warnings=warnings,
    )


def _validate_llm_scorecards(
    payload: dict,
    *,
    candidate_count: int,
    limit: int | None,
) -> list[CandidateScorecard]:
    raw_ranked = payload.get("ranked_candidates")
    if not isinstance(raw_ranked, list):
        raise ValueError("ranked_candidates must be a list")

    scorecards: list[CandidateScorecard] = []
    seen: set[int] = set()
    requested_limit = limit or candidate_count
    for raw_item in raw_ranked:
        if not isinstance(raw_item, dict):
            raise ValueError("ranked_candidates items must be objects")
        scorecard = _scorecard_from_llm_item(raw_item)
        if not 0 <= scorecard.candidate_index < candidate_count:
            continue
        if scorecard.candidate_index in seen:
            continue
        seen.add(scorecard.candidate_index)
        scorecards.append(scorecard)
        if len(scorecards) >= requested_limit:
            break

    if not scorecards:
        raise ValueError("LLM did not return any valid ranked_candidates")

    scorecards.sort(
        key=lambda item: (
            -item.match_score,
            -item.score_breakdown.get("role_alignment", 0),
            -item.score_breakdown.get("domain_alignment", 0),
            item.candidate_index,
        )
    )
    return scorecards[:requested_limit]


def _scorecard_from_llm_item(raw_item: dict) -> CandidateScorecard:
    index = int(raw_item.get("index"))
    breakdown = _normalize_score_breakdown(raw_item.get("score_breakdown"))
    score = _bounded_int(raw_item.get("match_score"), minimum=0, maximum=100)
    if score is None:
        score = _score_from_breakdown(breakdown)
    confidence_label = raw_item.get("confidence_label")
    if confidence_label not in {"strong", "medium", "limited", "weak"}:
        confidence_label = _confidence_label_for_score(score)
    return CandidateScorecard(
        candidate_index=index,
        match_score=score,
        confidence_label=confidence_label,
        score_breakdown=breakdown,
        matched_keywords=_dedupe_list(raw_item.get("matched_keywords", []))[:8],
        match_reasons=_dedupe_list(raw_item.get("match_reasons", []))[:6],
        risks=_dedupe_list(raw_item.get("risks", []))[:6],
        evidence_quotes=_dedupe_list(raw_item.get("evidence_quotes", []))[:6],
    )


def _normalize_score_breakdown(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {key: 0 for key in SCORE_BREAKDOWN_KEYS}
    normalized: dict[str, int] = {}
    for key in SCORE_BREAKDOWN_KEYS:
        maximum = 30 if key == "risk_penalty" else 25
        if key == "skill_evidence":
            maximum = 20
        elif key in {"seniority_and_work_type", "location_fit", "jd_evidence_quality"}:
            maximum = 10
        normalized[key] = _bounded_int(value.get(key), minimum=0, maximum=maximum) or 0
    return normalized


def _score_from_breakdown(breakdown: dict[str, int]) -> int:
    positive = sum(
        breakdown.get(key, 0)
        for key in [
            "role_alignment",
            "domain_alignment",
            "skill_evidence",
            "seniority_and_work_type",
            "location_fit",
            "jd_evidence_quality",
        ]
    )
    return max(0, min(100, positive - breakdown.get("risk_penalty", 0)))


def _bounded_int(value: object, *, minimum: int, maximum: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))


def _confidence_label_for_score(score: int) -> CandidateConfidenceLabel:
    if score >= 85:
        return "strong"
    if score >= 72:
        return "medium"
    if score >= 58:
        return "limited"
    return "weak"


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
