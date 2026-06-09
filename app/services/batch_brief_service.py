from __future__ import annotations

from collections import Counter

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.profile_review import ProfileSearchContext, ProfileSearchPlan
from app.schemas.search import SearchResultItem
from app.services.errors import JobAgentError
from app.services.job_search_service import search_jobs
from app.workflows.job_analysis_workflow import run_job_analysis_workflow

MIN_BRIEF_LIMIT = 1
MAX_BRIEF_LIMIT = 10
MAX_PROFILE_QUERY_TERMS = 20
MAX_PROFILE_QUERY_LENGTH = 300
MAX_CONSTRAINT_TERMS = 3
MAX_CONSTRAINT_LENGTH = 80


def build_brief_from_search(
    resume_text: str,
    query: str,
    provider: str = "mock",
    limit: int = 5,
    use_llm_jd: bool = False,
    profile_context: ProfileSearchContext | None = None,
) -> JobBriefReport:
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise JobAgentError("Resume text cannot be empty", "brief_resume_empty")

    search_plan = build_profile_search_plan(query, profile_context)
    effective_query = search_plan.effective_query
    if not effective_query:
        raise JobAgentError("Search query cannot be empty", "brief_query_empty")

    if limit < MIN_BRIEF_LIMIT or limit > MAX_BRIEF_LIMIT:
        raise JobAgentError(
            "Brief limit must be between 1 and 10",
            "brief_limit_invalid",
        )

    search_result = search_jobs(effective_query, provider=provider, limit=limit)
    return build_brief_from_jobs(
        resume_text=normalized_resume,
        query=effective_query,
        provider=search_result.provider,
        jobs=search_result.items,
        use_llm_jd=use_llm_jd,
    )


def build_profile_enhanced_query(
    query: str,
    profile_context: ProfileSearchContext | None,
) -> str:
    return build_profile_search_plan(query, profile_context).effective_query


def build_profile_search_plan(
    query: str,
    profile_context: ProfileSearchContext | None,
) -> ProfileSearchPlan:
    original_query = _normalize_term(query)
    warnings: list[str] = []
    role_terms: list[str] = []
    skill_terms: list[str] = []
    location_terms: list[str] = []
    constraint_terms: list[str] = []

    if profile_context is not None:
        confirmed_data = profile_context.user_confirmed_data
        role_terms = _normalize_terms(confirmed_data.target_roles)
        location_terms = _normalize_terms(confirmed_data.preferred_locations)
        skill_terms = _normalize_terms(
            [
                *confirmed_data.additional_skills,
                *profile_context.confirmed_profile.skills,
            ]
        )
        constraint_terms = _normalize_constraints(confirmed_data.constraints)

        if not any([role_terms, location_terms, skill_terms, constraint_terms]):
            warnings.append("profile_context is empty")
        if not role_terms:
            warnings.append("profile_context has no target roles")
        if not location_terms:
            warnings.append("profile_context has no preferred locations")
        if not skill_terms:
            warnings.append("profile_context has no skills")

    effective_terms = _build_effective_query_terms(
        original_query=original_query,
        role_terms=role_terms,
        location_terms=location_terms,
        skill_terms=skill_terms,
        constraint_terms=constraint_terms,
    )
    effective_query, was_truncated = _truncate_query(" ".join(effective_terms))
    if was_truncated:
        warnings.append("effective query was truncated to 300 characters")
    if not original_query and effective_query:
        warnings.append("effective query was generated only from profile context")

    return ProfileSearchPlan(
        original_query=original_query,
        effective_query=effective_query,
        role_terms=role_terms,
        skill_terms=skill_terms,
        location_terms=location_terms,
        constraint_terms=constraint_terms,
        warnings=warnings,
        profile_context_used=bool(
            role_terms or location_terms or skill_terms or constraint_terms
        ),
    )


def build_brief_from_jobs(
    resume_text: str,
    query: str,
    provider: str,
    jobs: list[SearchResultItem],
    use_llm_jd: bool = False,
) -> JobBriefReport:
    if not jobs:
        raise JobAgentError("No jobs available for brief generation", "brief_jobs_empty")

    recommendation_items: list[JobRecommendationItem] = []
    for job in jobs:
        job_text = select_job_text(job)
        workflow_result = run_job_analysis_workflow(
            resume_text=resume_text,
            jd_text=job_text,
            use_llm_jd=use_llm_jd,
            use_llm_resume_optimize=False,
            use_llm_project_challenge=False,
        )
        match_report = workflow_result.final_report.match_report
        recommendation_items.append(build_recommendation_item(job, match_report))

    sorted_items = sorted(
        recommendation_items,
        key=lambda item: item.fit_score,
        reverse=True,
    )
    reranked_items = [
        item.model_copy(update={"rank": index})
        for index, item in enumerate(sorted_items, start=1)
    ]

    top_skills = collect_top_skills(jobs)
    return JobBriefReport(
        query=query,
        provider=provider,
        total_jobs=len(jobs),
        recommended_jobs=reranked_items,
        top_skills=top_skills,
        market_summary=build_market_summary(query, provider, reranked_items, top_skills),
        application_strategy=build_application_strategy(reranked_items, top_skills),
        scoring_quality_summary=build_scoring_quality_summary(reranked_items),
    )


def select_job_text(job: SearchResultItem) -> str:
    if job.jd_text and job.jd_text.strip():
        return job.jd_text.strip()
    if job.snippet.strip():
        return job.snippet.strip()
    raise JobAgentError(
        "Job text is empty for brief scoring",
        "brief_job_text_empty",
    )


def get_scoring_quality(job: SearchResultItem) -> str:
    if job.quality_label:
        return job.quality_label
    if job.is_full_jd:
        return "full_jd"
    if job.jd_text and job.jd_text.strip():
        return "partial_jd"
    return "snippet_only"


def build_recommendation_item(job: SearchResultItem, match_report: MatchReport) -> JobRecommendationItem:
    return JobRecommendationItem(
        rank=0,
        job=job,
        match_report=match_report,
        fit_score=match_report.overall_score,
        advice=build_advice(match_report),
        scoring_quality=get_scoring_quality(job),
        fit_reasons=list(match_report.matched_points),
        risk_points=_dedupe_list([*match_report.risks, *match_report.missing_points]),
    )


def build_advice(match_report: MatchReport) -> str:
    if match_report.apply_recommendation.strip():
        return match_report.apply_recommendation.strip()
    if match_report.overall_score >= 75:
        return "Strong fit. Prioritize this role and tailor the resume before applying."
    if match_report.overall_score >= 55:
        return "Possible fit. Apply after tightening resume evidence around the missing points."
    return "Lower fit. Treat this as a stretch role unless you can quickly close the biggest gaps."


def collect_top_skills(jobs: list[SearchResultItem]) -> list[str]:
    ordered_skills: list[str] = []
    for job in jobs:
        for skill in job.skills:
            normalized_skill = skill.strip()
            if normalized_skill and normalized_skill not in ordered_skills:
                ordered_skills.append(normalized_skill)
            if len(ordered_skills) >= 10:
                return ordered_skills
    return ordered_skills


def build_market_summary(
    query: str,
    provider: str,
    recommendations: list[JobRecommendationItem],
    top_skills: list[str],
) -> str:
    top_score = recommendations[0].fit_score if recommendations else 0.0
    skills_summary = ", ".join(top_skills[:5]) if top_skills else "no shared skills extracted yet"
    return (
        f"Found {len(recommendations)} candidate jobs for query '{query}' via provider '{provider}'. "
        f"Top roles currently emphasize {skills_summary}. "
        f"The best current match scored {top_score:.1f}."
    )


def build_application_strategy(
    recommendations: list[JobRecommendationItem],
    top_skills: list[str],
) -> list[str]:
    strategy: list[str] = []
    if recommendations:
        top_job = recommendations[0]
        strategy.append(
            f"Prioritize rank #{top_job.rank} first because it currently scores {top_job.fit_score:.1f}."
        )

    quality_counts = Counter(item.scoring_quality for item in recommendations)
    if (
        quality_counts.get("snippet_only", 0) > 0
        or quality_counts.get("partial_jd", 0) > 0
        or quality_counts.get("external_link_only", 0) > 0
    ):
        strategy.append(
            "For partial_jd, external_link_only, or snippet_only roles, confirm a fuller JD before investing in heavy resume tailoring."
        )

    if top_skills:
        strategy.append(
            f"Highlight repeat market signals in your resume and outreach: {', '.join(top_skills[:5])}."
        )
    else:
        strategy.append(
            "Review the top-ranked roles manually and extract repeated skills before tailoring your resume."
        )

    return strategy[:3]


def build_scoring_quality_summary(recommendations: list[JobRecommendationItem]) -> str:
    counts = Counter(item.scoring_quality for item in recommendations)
    summary = (
        f"Scoring quality mix: full_jd={counts.get('full_jd', 0)}, "
        f"partial_jd={counts.get('partial_jd', 0)}, "
        f"external_link_only={counts.get('external_link_only', 0)}, "
        f"snippet_only={counts.get('snippet_only', 0)}."
    )
    if counts.get("external_link_only", 0) > 0 or counts.get("snippet_only", 0) > 0:
        summary += (
            f" 本次推荐中 {counts.get('full_jd', 0)} 个岗位来自完整 JD，"
            f"{counts.get('external_link_only', 0) + counts.get('snippet_only', 0)} 个岗位只含外链或摘要，"
            "摘要型岗位评分可信度较低。"
        )
    return summary


def _dedupe_list(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        normalized_item = item.strip()
        if normalized_item and normalized_item not in deduped:
            deduped.append(normalized_item)
    return deduped


def _normalize_term(term: str) -> str:
    return " ".join(term.strip().split())


def _normalize_terms(terms: list[str]) -> list[str]:
    normalized_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized_term = _normalize_term(term)
        key = normalized_term.lower()
        if not normalized_term or key in seen:
            continue
        normalized_terms.append(normalized_term)
        seen.add(key)
    return normalized_terms


def _normalize_constraints(constraints: list[str]) -> list[str]:
    normalized_constraints: list[str] = []
    seen: set[str] = set()
    for constraint in constraints:
        normalized_constraint = _normalize_term(constraint)
        if len(normalized_constraint) > MAX_CONSTRAINT_LENGTH:
            normalized_constraint = _truncate_at_word_boundary(
                normalized_constraint,
                MAX_CONSTRAINT_LENGTH,
            )
        key = normalized_constraint.lower()
        if not normalized_constraint or key in seen:
            continue
        normalized_constraints.append(normalized_constraint)
        seen.add(key)
        if len(normalized_constraints) >= MAX_CONSTRAINT_TERMS:
            break
    return normalized_constraints


def _build_effective_query_terms(
    *,
    original_query: str,
    role_terms: list[str],
    location_terms: list[str],
    skill_terms: list[str],
    constraint_terms: list[str],
) -> list[str]:
    effective_terms: list[str] = []
    seen: set[str] = set()
    if original_query:
        _append_effective_query_term(effective_terms, seen, original_query)

    for terms in [role_terms, location_terms, skill_terms, constraint_terms]:
        for term in terms:
            _append_effective_query_term(effective_terms, seen, term)
            if len(effective_terms) >= MAX_PROFILE_QUERY_TERMS:
                return effective_terms
    return effective_terms


def _append_effective_query_term(terms: list[str], seen: set[str], term: str) -> None:
    normalized_term = _normalize_term(term)
    if not normalized_term:
        return

    key = normalized_term.lower()
    if key in seen:
        return

    terms.append(normalized_term)
    seen.add(key)
    for token in normalized_term.split():
        seen.add(token.lower())


def _truncate_query(query: str) -> tuple[str, bool]:
    normalized_query = query.strip()
    if len(normalized_query) <= MAX_PROFILE_QUERY_LENGTH:
        return normalized_query, False

    return _truncate_at_word_boundary(normalized_query, MAX_PROFILE_QUERY_LENGTH), True


def _truncate_at_word_boundary(text: str, max_length: int) -> str:
    truncated = text[:max_length].rstrip()
    if " " in truncated:
        return truncated.rsplit(" ", 1)[0].strip()
    return truncated
