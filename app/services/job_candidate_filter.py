from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_search_intent import is_generic_tool_term
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

LOCATION_ALIASES = {
    "shenzhen": ["shenzhen", "深圳", "深圳市"],
    "china": ["china", "中国"],
    "beijing": ["beijing", "北京", "北京市"],
    "shanghai": ["shanghai", "上海", "上海市"],
    "guangzhou": ["guangzhou", "广州", "广州市"],
    "hangzhou": ["hangzhou", "杭州", "杭州市"],
}

SIGNAL_VARIANTS = [
    (("physiological signal", "biosignal", "bio-signal"), ["生理信号", "信号处理"]),
    (("signal processing",), ["信号处理"]),
    (("health", "healthcare"), ["健康", "医疗"]),
    (("biomedical", "medical"), ["生物医学", "医疗"]),
    (("algorithm", "algorithms"), ["算法"]),
    (("artificial intelligence", "machine learning", "deep learning"), ["人工智能", "机器学习", "深度学习"]),
    (("data analysis", "data analyst", "data science"), ["数据分析"]),
    (("intern", "internship"), ["实习", "实习生"]),
    (("backend", "back-end"), ["后端"]),
    (("frontend", "front-end"), ["前端"]),
    (("marketing", "market research", "consumer insight"), ["市场", "市场调研", "用户研究"]),
    (("finance", "investment"), ["金融", "投资"]),
    (("quant",), ["量化"]),
]

HELPER_WARNING_FRAGMENTS = [
    "browser helper",
    "platform cookies",
    "local boss browser session",
    "cookies were not sent",
    "cookies are not stored",
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
    signals = _ranking_signals(confirmed_profile, search_plan)
    avoid_signals = [item.lower() for item in search_plan.avoid_signals]
    scored: list[tuple[int, int, int, int, CandidateScorecard]] = []
    for index, candidate in enumerate(candidates):
        scorecard = _deterministic_scorecard(
            index,
            candidate,
            confirmed_profile=confirmed_profile,
            search_plan=search_plan,
            signals=signals,
            avoid_signals=avoid_signals,
        )
        scored.append(
            (
                index,
                scorecard.match_score,
                scorecard.score_breakdown.get("role_alignment", 0),
                scorecard.score_breakdown.get("domain_alignment", 0),
                scorecard,
            )
        )
    scored.sort(key=lambda item: (-item[1], -item[2], -item[3], item[0]))
    selected = scored[:limit] if limit is not None else scored
    ranked_indexes = [index for index, _score, _role, _domain, _scorecard in selected]
    scorecards = [scorecard for _index, _score, _role, _domain, scorecard in selected]

    warnings: list[str] = []
    if not signals:
        warnings.append("Candidate ranking used limited profile signals.")
    return CandidateFilterResult(
        selected_candidates=[candidates[index] for index in ranked_indexes],
        selected_indexes=ranked_indexes,
        scorecards=scorecards,
        mode="deterministic",
        fallback_reason=None,
        quality_warnings=warnings,
    )


def _deterministic_scorecard(
    index: int,
    candidate: RawJobCandidate,
    *,
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    signals: list[str],
    avoid_signals: list[str],
) -> CandidateScorecard:
    text = _candidate_text(candidate)
    title_text = (candidate.title or "").lower()
    matched = [signal for signal in signals if _contains_signal(text, signal)]
    domain_terms = _domain_terms(confirmed_profile, search_plan)
    domain_matches = [term for term in domain_terms if _contains_signal(text, term)]
    skill_terms = _skill_terms(confirmed_profile, search_plan)
    skill_matches = [term for term in skill_terms if _contains_signal(text, term)]

    role_alignment = _role_alignment_score(confirmed_profile, search_plan, title_text, text)
    domain_alignment = _domain_alignment_score(domain_matches)
    skill_evidence = min(20, len(skill_matches) * 4 + len([term for term in skill_matches if not is_generic_tool_term(term)]) * 2)
    seniority_and_work_type, seniority_risks = _seniority_score_and_risks(confirmed_profile, candidate, text)
    location_fit, location_risks = _location_score_and_risks(confirmed_profile, candidate)
    jd_evidence_quality, evidence_risks = _jd_evidence_score_and_risks(candidate)
    avoid_hits = [signal for signal in avoid_signals if signal and signal in text]
    risk_penalty = min(
        30,
        len(avoid_hits) * 6
        + len(seniority_risks) * 5
        + len(location_risks) * 3
        + len(evidence_risks) * 3
        + (6 if role_alignment <= 7 and domain_alignment <= 9 else 0),
    )
    breakdown = {
        "role_alignment": role_alignment,
        "domain_alignment": domain_alignment,
        "skill_evidence": skill_evidence,
        "seniority_and_work_type": seniority_and_work_type,
        "location_fit": location_fit,
        "jd_evidence_quality": jd_evidence_quality,
        "risk_penalty": risk_penalty,
    }
    score = _score_from_breakdown(breakdown)
    risks = _dedupe_list(
        avoid_hits
        + seniority_risks
        + location_risks
        + evidence_risks
        + (["Weak role/domain evidence for this profile."] if role_alignment <= 7 and domain_alignment <= 9 else [])
    )
    reasons = _deterministic_reasons(
        role_alignment=role_alignment,
        domain_alignment=domain_alignment,
        skill_evidence=skill_evidence,
        matched=matched,
        domain_matches=domain_matches,
        skill_matches=skill_matches,
    )
    return CandidateScorecard(
        candidate_index=index,
        match_score=score,
        confidence_label=_confidence_label_for_score(score),
        score_breakdown=breakdown,
        matched_keywords=_dedupe_list(matched + domain_matches + skill_matches)[:8],
        match_reasons=reasons,
        risks=risks[:6],
        evidence_quotes=_evidence_quotes(candidate, matched + domain_matches + skill_matches),
    )


def _ranking_signals(confirmed_profile: ConfirmedProfile, search_plan: JobSearchPlan) -> list[str]:
    return _dedupe_list(
        confirmed_profile.target_roles
        + confirmed_profile.target_directions
        + confirmed_profile.search_keywords
        + confirmed_profile.core_skills
        + confirmed_profile.supporting_skills
        + search_plan.must_have_signals
    )


def _candidate_text(candidate: RawJobCandidate) -> str:
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


def _contains_signal(text: str, signal: str) -> bool:
    return any(variant and variant.lower() in text for variant in _signal_variants(signal))


def _signal_variants(signal: str) -> list[str]:
    normalized = signal.strip()
    if not normalized:
        return []
    lowered = normalized.lower()
    variants = [normalized]
    for needles, additions in SIGNAL_VARIANTS:
        if any(needle in lowered for needle in needles):
            variants.extend(additions)
    if "ai" in lowered.split() or lowered.startswith("ai "):
        variants.extend(["AI", "人工智能"])
    return _dedupe_list(variants)


def _domain_terms(confirmed_profile: ConfirmedProfile, search_plan: JobSearchPlan) -> list[str]:
    intent = search_plan.search_intent
    return _dedupe_list(
        confirmed_profile.target_directions
        + confirmed_profile.search_keywords
        + (intent.industry_domains if intent else [])
        + (intent.evidence_skills if intent else [])
    )


def _skill_terms(confirmed_profile: ConfirmedProfile, search_plan: JobSearchPlan) -> list[str]:
    intent = search_plan.search_intent
    return _dedupe_list(
        confirmed_profile.core_skills
        + confirmed_profile.supporting_skills
        + search_plan.must_have_signals
        + (intent.generic_tools if intent else [])
    )


def _role_alignment_score(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    title_text: str,
    text: str,
) -> int:
    roles = _dedupe_list(confirmed_profile.target_roles + search_plan.target_roles)
    if any(role.lower() in title_text for role in roles):
        return 25
    if any(role.lower() in text for role in roles):
        return 20
    role_tokens = {
        variant.lower()
        for role in roles
        for token in role.lower().replace("/", " ").split()
        if token not in {"intern", "internship", "assistant"}
        for variant in _signal_variants(token)
        if len(variant) >= 2
    }
    title_hits = sum(1 for token in role_tokens if token in title_text)
    text_hits = sum(1 for token in role_tokens if token in text)
    if title_hits >= 2:
        return 18
    if title_hits == 1:
        return 12
    if text_hits:
        return 8
    return 3 if roles else 8


def _domain_alignment_score(domain_matches: list[str]) -> int:
    distinctive_matches = [term for term in domain_matches if not is_generic_tool_term(term)]
    if len(distinctive_matches) >= 4:
        return 25
    if len(distinctive_matches) >= 2:
        return 18
    if distinctive_matches:
        return 11
    return 0


def _seniority_score_and_risks(
    confirmed_profile: ConfirmedProfile,
    candidate: RawJobCandidate,
    text: str,
) -> tuple[int, list[str]]:
    profile_level = " ".join(confirmed_profile.target_roles + confirmed_profile.search_keywords).lower()
    candidate_title = (candidate.title or "").lower()
    wants_early = any(token in profile_level for token in ["intern", "assistant", "graduate", "entry"])
    candidate_early = any(token in text for token in ["intern", "assistant", "graduate", "entry level", "junior"])
    candidate_senior = any(token in candidate_title for token in ["senior", "lead", "principal", "manager", "director"])
    if wants_early and candidate_early:
        return 10, []
    if wants_early and candidate_senior:
        return 2, ["Candidate appears more senior than the target profile."]
    if candidate_senior:
        return 5, ["Candidate seniority may be higher than the profile target."]
    return 7, []


def _location_score_and_risks(
    confirmed_profile: ConfirmedProfile,
    candidate: RawJobCandidate,
) -> tuple[int, list[str]]:
    location = (candidate.location or "").lower()
    preferred = [item.lower() for item in confirmed_profile.preferred_locations]
    arrangements = " ".join(confirmed_profile.work_arrangements).lower()
    if not location:
        return 5, ["Candidate location is missing."]
    if "remote" in location and "remote" in arrangements:
        return 10, []
    if any(_location_matches(location, pref) for pref in preferred):
        return 10, []
    if "remote" in location:
        return 7, []
    return 4, ["Candidate location may not match preferred locations."]


def _location_matches(candidate_location: str, preferred_location: str) -> bool:
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


def _jd_evidence_score_and_risks(candidate: RawJobCandidate) -> tuple[int, list[str]]:
    evidence_text = " ".join([candidate.snippet or "", candidate.raw_description or ""]).strip()
    risks: list[str] = []
    if not candidate.source_url:
        risks.append("Candidate source URL is missing.")
    provider_warnings = [
        warning
        for warning in candidate.provider_warnings
        if not _is_boilerplate_provider_warning(warning)
    ]
    if provider_warnings:
        risks.extend(provider_warnings[:2])
    if len(evidence_text) >= 180 and candidate.source_url:
        return (8 if provider_warnings else 10), risks
    if len(evidence_text) >= 60:
        return 6, risks
    risks.append("Candidate JD evidence is sparse.")
    return 3, risks


def _is_boilerplate_provider_warning(warning: str) -> bool:
    normalized = warning.lower()
    return any(fragment in normalized for fragment in HELPER_WARNING_FRAGMENTS)


def _deterministic_reasons(
    *,
    role_alignment: int,
    domain_alignment: int,
    skill_evidence: int,
    matched: list[str],
    domain_matches: list[str],
    skill_matches: list[str],
) -> list[str]:
    reasons: list[str] = []
    if role_alignment >= 20:
        reasons.append("Strong role-title alignment with the confirmed profile.")
    elif role_alignment >= 12:
        reasons.append("Partial role-function alignment with the confirmed profile.")
    if domain_alignment >= 18:
        reasons.append("Strong domain evidence overlap: " + ", ".join(domain_matches[:4]) + ".")
    elif domain_alignment >= 11:
        reasons.append("Some domain evidence overlap: " + ", ".join(domain_matches[:3]) + ".")
    if skill_evidence:
        reasons.append("Matched skill/search signals: " + ", ".join(skill_matches[:5] or matched[:5]) + ".")
    if not reasons:
        reasons.append("Candidate remains in the pool but has limited direct profile evidence.")
    return _dedupe_list(reasons)[:6]


def _evidence_quotes(candidate: RawJobCandidate, terms: list[str]) -> list[str]:
    sources = [
        candidate.title or "",
        candidate.snippet or "",
        candidate.raw_description or "",
    ]
    quotes: list[str] = []
    lowered_terms = [term.lower() for term in _dedupe_list(terms) if term]
    for source in sources:
        text = " ".join(source.split())
        lowered = text.lower()
        if text and (not lowered_terms or any(term in lowered for term in lowered_terms)):
            quotes.append(text[:220])
        if len(quotes) >= 3:
            break
    return _dedupe_list(quotes)


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
