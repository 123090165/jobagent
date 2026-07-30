"""从职位文本、画像证据和 mission 快照计算候选分数、证据与未知项。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job import JobAnalysis, JDRequirement
from app.services.job_candidate_constraints import candidate_text, location_matches
from app.services.job_search_intent import is_generic_tool_term
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate

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


class CandidateScorecard(BaseModel):
    """保存候选各评分维度、证据、风险和最终分数。"""
    candidate_index: int
    match_score: int = Field(ge=0, le=100)
    confidence_label: CandidateConfidenceLabel
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    matched_keywords: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class JobMatchContext:
    """汇总一个候选的 JD、画像证据、mission 约束和来源信息。"""
    confirmed_profile: ConfirmedProfile
    search_plan: JobSearchPlan
    candidate: RawJobCandidate
    analysis: JobAnalysis
    profile_evidence_text: str = ""


class CandidateFilterResult(BaseModel):
    selected_candidates: list[RawJobCandidate] = Field(default_factory=list)
    selected_indexes: list[int] = Field(default_factory=list)
    scorecards: list[CandidateScorecard] = Field(default_factory=list)
    mode: Literal["deterministic", "llm", "fallback"]
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, object] = Field(default_factory=dict)


def deterministic_filter(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    candidates: list[RawJobCandidate],
    *,
    limit: int | None = None,
    allowed_indexes: set[int] | None = None,
) -> CandidateFilterResult:
    """执行硬约束和本地评分，在没有 LLM 时仍产生稳定候选顺序。"""
    signals = _ranking_signals(confirmed_profile, search_plan)
    avoid_signals = [item.lower() for item in search_plan.avoid_signals]
    scored: list[tuple[int, int, int, int, CandidateScorecard]] = []
    for index, candidate in enumerate(candidates):
        if allowed_indexes is not None and index not in allowed_indexes:
            continue
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


def build_candidate_scorecard(
    candidate_index: int,
    candidate: RawJobCandidate,
    *,
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
) -> CandidateScorecard:
    """根据召回阶段可见文本计算初始候选评分卡。"""
    return _deterministic_scorecard(
        candidate_index,
        candidate,
        confirmed_profile=confirmed_profile,
        search_plan=search_plan,
        signals=_ranking_signals(confirmed_profile, search_plan),
        avoid_signals=[item.lower() for item in search_plan.avoid_signals],
    )


def build_final_candidate_scorecard(
    candidate_index: int,
    context: JobMatchContext,
) -> CandidateScorecard:
    """使用结构化 JD 证据重算最终评分，并保留召回分作诊断。"""
    scorecard = build_candidate_scorecard(
        candidate_index,
        context.candidate,
        confirmed_profile=context.confirmed_profile,
        search_plan=context.search_plan,
    )
    return _apply_requirement_assessment(scorecard, context)


def contains_signal(text: str, signal: str) -> bool:
    """判断规范化信号是否作为完整词或短语出现在候选文本中。"""
    return any(variant and variant.lower() in text for variant in _signal_variants(signal))


def score_from_breakdown(breakdown: dict[str, int]) -> int:
    """按固定权重把各评分维度合成为 0–100 分。"""
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


def confidence_label_for_score(score: int) -> CandidateConfidenceLabel:
    """把数值分数映射为前端使用的置信度标签。"""
    if score >= 85:
        return "strong"
    if score >= 72:
        return "medium"
    if score >= 58:
        return "limited"
    return "weak"


def dedupe_list(values: list[str] | object) -> list[str]:
    """保持原顺序去重非空文本。"""
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


def _deterministic_scorecard(
    index: int,
    candidate: RawJobCandidate,
    *,
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    signals: list[str],
    avoid_signals: list[str],
) -> CandidateScorecard:
    text = candidate_text(candidate)
    title_text = (candidate.title or "").lower()
    matched = [signal for signal in signals if contains_signal(text, signal)]
    domain_terms = _domain_terms(confirmed_profile, search_plan)
    domain_matches = [term for term in domain_terms if contains_signal(text, term)]
    skill_terms = _skill_terms(confirmed_profile, search_plan)
    skill_matches = [term for term in skill_terms if contains_signal(text, term)]

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
    score = score_from_breakdown(breakdown)
    risks = dedupe_list(
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
        confidence_label=confidence_label_for_score(score),
        score_breakdown=breakdown,
        matched_keywords=dedupe_list(matched + domain_matches + skill_matches)[:8],
        match_reasons=reasons,
        risks=risks[:6],
        evidence_quotes=_evidence_quotes(candidate, matched + domain_matches + skill_matches),
    )


def _ranking_signals(confirmed_profile: ConfirmedProfile, search_plan: JobSearchPlan) -> list[str]:
    return dedupe_list(
        confirmed_profile.target_roles
        + confirmed_profile.target_directions
        + confirmed_profile.search_keywords
        + confirmed_profile.core_skills
        + confirmed_profile.supporting_skills
        + search_plan.must_have_signals
    )


def _apply_requirement_assessment(
    scorecard: CandidateScorecard,
    context: JobMatchContext,
) -> CandidateScorecard:
    skill_requirements = [
        requirement
        for requirement in context.analysis.requirements
        if requirement.category == "skill"
    ]
    scored_skill_requirements = [
        requirement
        for requirement in skill_requirements
        if requirement.necessity in {"required", "preferred"}
    ]
    profile_text = _profile_evidence_text(context)
    unresolved_requirements = [
        requirement
        for requirement in context.analysis.requirements
        if requirement.category in {"experience", "education", "work_authorization", "other"}
        and requirement.necessity == "required"
        and not contains_signal(profile_text, requirement.name)
    ]
    if not scored_skill_requirements and not unresolved_requirements:
        return scorecard

    supported = [
        requirement
        for requirement in scored_skill_requirements
        if contains_signal(profile_text, requirement.name)
    ]
    unknown_required = [
        requirement
        for requirement in scored_skill_requirements
        if requirement.necessity == "required" and requirement not in supported
    ]
    supported_required = [
        requirement for requirement in supported if requirement.necessity == "required"
    ]
    supported_preferred = [
        requirement for requirement in supported if requirement.necessity == "preferred"
    ]

    requirement_skill_score = min(
        20,
        len(supported_required) * 5
        + len(supported_preferred) * 2,
    )
    breakdown = dict(scorecard.score_breakdown)
    if scored_skill_requirements:
        breakdown["skill_evidence"] = requirement_skill_score
    score = score_from_breakdown(breakdown)

    reasons = list(scorecard.match_reasons)
    if supported_required:
        reasons.insert(
            0,
            "Profile evidence supports required skills: "
            + ", ".join(requirement.name for requirement in supported_required[:4])
            + ".",
        )
    if supported_preferred:
        reasons.append(
            "Profile evidence supports preferred skills: "
            + ", ".join(requirement.name for requirement in supported_preferred[:3])
            + "."
        )

    unknowns = [
        f"Profile evidence was not found for required skill: {requirement.name}."
        for requirement in unknown_required[:5]
    ]
    unknowns.extend(
        f"Needs confirmation for {requirement.category}: {requirement.name}."
        for requirement in unresolved_requirements[:3]
    )
    evidence_quotes = [
        requirement.evidence_quote
        for requirement in [
            *supported_required,
            *supported_preferred,
            *unknown_required,
            *unresolved_requirements,
        ]
        if requirement.evidence_quote
    ]
    confidence = confidence_label_for_score(score)
    if unresolved_requirements or (
        unknown_required and len(unknown_required) >= len(supported_required)
    ):
        if confidence in {"medium", "strong"}:
            confidence = "limited"

    return scorecard.model_copy(
        update={
            "match_score": score,
            "confidence_label": confidence,
            "score_breakdown": breakdown,
            "match_reasons": dedupe_list(reasons)[:6],
            "evidence_quotes": dedupe_list(
                [*evidence_quotes, *scorecard.evidence_quotes]
            )[:4],
            "unknowns": dedupe_list([*scorecard.unknowns, *unknowns])[:6],
        }
    )


def _profile_evidence_text(context: JobMatchContext) -> str:
    profile = context.confirmed_profile
    return " ".join(
        [
            profile.summary,
            *profile.target_roles,
            *profile.target_directions,
            *profile.core_skills,
            *profile.supporting_skills,
            *profile.strengths,
            context.profile_evidence_text,
        ]
    ).casefold()


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
    return dedupe_list(variants)


def _domain_terms(confirmed_profile: ConfirmedProfile, search_plan: JobSearchPlan) -> list[str]:
    intent = search_plan.search_intent
    return dedupe_list(
        confirmed_profile.target_directions
        + confirmed_profile.search_keywords
        + (intent.industry_domains if intent else [])
        + (intent.evidence_skills if intent else [])
    )


def _skill_terms(confirmed_profile: ConfirmedProfile, search_plan: JobSearchPlan) -> list[str]:
    intent = search_plan.search_intent
    return dedupe_list(
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
    roles = dedupe_list(confirmed_profile.target_roles + search_plan.target_roles)
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
    if any(location_matches(location, pref) for pref in preferred):
        return 10, []
    if "remote" in location:
        return 7, []
    return 4, ["Candidate location may not match preferred locations."]


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
    return dedupe_list(reasons)[:6]


def _evidence_quotes(candidate: RawJobCandidate, terms: list[str]) -> list[str]:
    sources = [
        candidate.title or "",
        candidate.snippet or "",
        candidate.raw_description or "",
    ]
    quotes: list[str] = []
    lowered_terms = [term.lower() for term in dedupe_list(terms) if term]
    for source in sources:
        text = " ".join(source.split())
        lowered = text.lower()
        if text and (not lowered_terms or any(term in lowered for term in lowered_terms)):
            quotes.append(text[:220])
        if len(quotes) >= 3:
            break
    return dedupe_list(quotes)
