from __future__ import annotations

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.services.brief_run_storage_service import get_brief_run
from app.services.errors import JobAgentError

MAX_RERANK_LIMIT = 50
QUALITY_BONUS = {
    "full_jd": 5.0,
    "partial_jd": 1.0,
    "external_link_only": -5.0,
    "snippet_only": -3.0,
    "invalid": -6.0,
}


def rerank_brief_run(
    run_id: str,
    require_full_jd: bool = False,
    exclude_external_link_only: bool = False,
    location_keywords: list[str] | None = None,
    include_keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
    min_fit_score: float | None = None,
    limit: int | None = None,
) -> JobBriefReport:
    stored = get_brief_run(run_id)
    if stored is None:
        raise JobAgentError("Brief run not found", "brief_run_not_found", status_code=404)

    normalized_limit = _normalize_limit(limit)
    location_terms = _normalize_keywords(location_keywords)
    include_terms = _normalize_keywords(include_keywords)
    exclude_terms = _normalize_keywords(exclude_keywords)
    brief = JobBriefReport.model_validate(stored["brief"])

    filtered_items: list[tuple[float, JobRecommendationItem]] = []
    for item in brief.recommended_jobs:
        if require_full_jd and item.scoring_quality != "full_jd":
            continue
        if exclude_external_link_only and item.scoring_quality == "external_link_only":
            continue
        if min_fit_score is not None and item.fit_score < float(min_fit_score):
            continue
        if exclude_terms and item_matches_keywords(item, exclude_terms):
            continue

        score = compute_rerank_score(
            item,
            location_keywords=location_terms,
            include_keywords=include_terms,
        )
        filtered_items.append((score, item))

    if not filtered_items:
        raise JobAgentError("Rerank produced no results", "brief_rerank_no_results")

    reranked_items = [
        item
        for _, item in sorted(
            filtered_items,
            key=lambda pair: (pair[0], pair[1].fit_score, -pair[1].rank),
            reverse=True,
        )[:normalized_limit if normalized_limit is not None else None]
    ]

    return _rebuild_report(brief, reranked_items)


def compute_rerank_score(
    item: JobRecommendationItem,
    *,
    location_keywords: list[str] | None = None,
    include_keywords: list[str] | None = None,
) -> float:
    score = float(item.fit_score)
    score += QUALITY_BONUS.get(item.scoring_quality, 0.0)

    if location_keywords and item_matches_location(item, location_keywords):
        score += 3.0
    if include_keywords:
        include_hits = sum(1 for keyword in include_keywords if item_matches_keywords(item, [keyword]))
        score += include_hits * 2.0
    return score


def item_matches_location(item: JobRecommendationItem, keywords: list[str]) -> bool:
    location_text = (item.job.location or "").lower()
    return any(keyword in location_text for keyword in keywords)


def item_matches_keywords(item: JobRecommendationItem, keywords: list[str]) -> bool:
    searchable_text = "\n".join(
        [
            item.job.title,
            item.job.company,
            item.job.location,
            item.job.url,
            item.job.snippet,
            item.advice,
            "\n".join(item.fit_reasons),
            "\n".join(item.risk_points),
        ]
    ).lower()
    return any(keyword in searchable_text for keyword in keywords)


def rebuild_scoring_quality_summary(items: list[JobRecommendationItem]) -> str:
    counts = {
        "full_jd": 0,
        "partial_jd": 0,
        "external_link_only": 0,
        "snippet_only": 0,
        "invalid": 0,
    }
    for item in items:
        if item.scoring_quality in counts:
            counts[item.scoring_quality] += 1
    summary = (
        f"Scoring quality mix: full_jd={counts['full_jd']}, "
        f"partial_jd={counts['partial_jd']}, "
        f"external_link_only={counts['external_link_only']}, "
        f"snippet_only={counts['snippet_only']}."
    )
    if counts["external_link_only"] > 0 or counts["snippet_only"] > 0:
        summary += (
            f" 本次推荐中 {counts['full_jd']} 个岗位来自完整 JD，"
            f"{counts['external_link_only'] + counts['snippet_only']} 个岗位只含外链或摘要，"
            "摘要型岗位评分可信度较低。"
        )
    return summary


def _rebuild_report(base_report: JobBriefReport, items: list[JobRecommendationItem]) -> JobBriefReport:
    reranked_items = [
        item.model_copy(update={"rank": index})
        for index, item in enumerate(items, start=1)
    ]
    top_skills: list[str] = []
    for item in reranked_items:
        for skill in item.job.skills:
            normalized = skill.strip()
            if normalized and normalized not in top_skills:
                top_skills.append(normalized)
            if len(top_skills) >= 10:
                break
        if len(top_skills) >= 10:
            break

    return JobBriefReport(
        query=base_report.query,
        provider=base_report.provider,
        total_jobs=len(reranked_items),
        recommended_jobs=reranked_items,
        top_skills=top_skills,
        market_summary=(
            f"Found {len(reranked_items)} candidate jobs for query '{base_report.query}' via provider "
            f"'{base_report.provider}'. This report was reranked from an existing brief run without re-searching."
        ),
        application_strategy=base_report.application_strategy,
        scoring_quality_summary=rebuild_scoring_quality_summary(reranked_items),
    )


def _normalize_keywords(values: list[str] | None) -> list[str]:
    if not values:
        return []
    keywords: list[str] = []
    for value in values:
        normalized = (value or "").strip().lower()
        if normalized and normalized not in keywords:
            keywords.append(normalized)
    return keywords


def _normalize_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if limit < 1 or limit > MAX_RERANK_LIMIT:
        raise JobAgentError(
            "Rerank limit must be between 1 and 50",
            "brief_rerank_limit_invalid",
        )
    return limit
