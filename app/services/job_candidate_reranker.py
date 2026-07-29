from __future__ import annotations

import json

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_candidate_constraints import candidate_text
from app.services.job_candidate_scoring import (
    SCORE_BREAKDOWN_KEYS,
    CandidateScorecard,
    confidence_label_for_score,
    contains_signal,
    dedupe_list,
    score_from_breakdown,
)
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate

LLM_CANDIDATE_RANKING_SYSTEM_PROMPT = """
You are ranking existing job candidates for one confirmed user profile.

Hard guardrails:
- Rank only the candidates in the input. Do not invent, merge, rewrite, or drop candidates because metadata is incomplete.
- Missing company, location, source_url, or sparse JD text is a confidence/risk issue, not an automatic rejection.
- Prefer role/domain evidence over generic tool overlap. Python, MATLAB, PyTorch, SQL, FastAPI, Docker, Git, and similar tool words are weak signals unless the role/domain also matches.
- Use only evidence visible in the candidate title, company, location, snippet, raw_description, provider_warnings, confirmed profile, and search plan.
- Make the same decision for the same input: use integer scores, no randomness, no prose outside JSON, and break exact score ties by lower candidate index.
- Treat search_plan.must_have_signals and target_roles as the user's current mission, not merely resume evidence.
- Apply a clear risk penalty when candidate title or duties match search_plan.avoid_signals. State the violated mission signal in risks.

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


def build_rerank_prompt(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    candidates: list[RawJobCandidate],
    *,
    requested_limit: int,
) -> tuple[str, str]:
    candidates_json = json.dumps(
        [
            {**candidate.model_dump(mode="json"), "index": index}
            for index, candidate in enumerate(candidates)
        ],
        ensure_ascii=False,
    )
    user_prompt = (
        f"Requested result limit: {requested_limit}\n\n"
        "Confirmed profile JSON:\n"
        f"{json.dumps(confirmed_profile.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        "Search plan JSON:\n"
        f"{search_plan.model_dump_json()}\n\n"
        "Candidates JSON:\n"
        f"{candidates_json}"
    )
    return user_prompt, candidates_json


def validate_llm_scorecards(
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


def apply_mission_penalties(
    scorecards: list[CandidateScorecard],
    candidates: list[RawJobCandidate],
    avoid_signals: list[str],
) -> list[CandidateScorecard]:
    adjusted: list[CandidateScorecard] = []
    for scorecard in scorecards:
        text = candidate_text(candidates[scorecard.candidate_index])
        hits = [signal for signal in avoid_signals if signal and contains_signal(text, signal)]
        if not hits:
            adjusted.append(scorecard)
            continue
        breakdown = dict(scorecard.score_breakdown)
        breakdown["risk_penalty"] = min(
            30,
            max(breakdown.get("risk_penalty", 0), len(hits) * 6),
        )
        score = score_from_breakdown(breakdown)
        adjusted.append(
            scorecard.model_copy(
                update={
                    "match_score": score,
                    "confidence_label": confidence_label_for_score(score),
                    "score_breakdown": breakdown,
                    "risks": dedupe_list(
                        scorecard.risks
                        + [f"Conflicts with excluded mission signal: {hit}" for hit in hits]
                    )[:6],
                }
            )
        )
    adjusted.sort(
        key=lambda item: (
            -item.match_score,
            -item.score_breakdown.get("role_alignment", 0),
            -item.score_breakdown.get("domain_alignment", 0),
            item.candidate_index,
        )
    )
    return adjusted


def _scorecard_from_llm_item(raw_item: dict) -> CandidateScorecard:
    index = int(raw_item.get("index"))
    breakdown = _normalize_score_breakdown(raw_item.get("score_breakdown"))
    score = _bounded_int(raw_item.get("match_score"), minimum=0, maximum=100)
    if score is None:
        score = score_from_breakdown(breakdown)
    confidence_label = raw_item.get("confidence_label")
    if confidence_label not in {"strong", "medium", "limited", "weak"}:
        confidence_label = confidence_label_for_score(score)
    return CandidateScorecard(
        candidate_index=index,
        match_score=score,
        confidence_label=confidence_label,
        score_breakdown=breakdown,
        matched_keywords=dedupe_list(raw_item.get("matched_keywords", []))[:8],
        match_reasons=dedupe_list(raw_item.get("match_reasons", []))[:6],
        risks=dedupe_list(raw_item.get("risks", []))[:6],
        evidence_quotes=dedupe_list(raw_item.get("evidence_quotes", []))[:6],
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


def _bounded_int(value: object, *, minimum: int, maximum: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))
