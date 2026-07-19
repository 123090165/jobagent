from __future__ import annotations

from collections import Counter
from uuid import NAMESPACE_URL, uuid5

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import JobSearchResult
from app.services.job_candidate_filter import (
    CandidateScorecard,
    build_candidate_scorecard,
)
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_recall_metrics import candidate_recall_key


def _build_local_mock_results(
    *,
    query: str,
    locations: list[str],
    target_roles: list[str],
    keywords: list[str],
    confirmed_profile: ConfirmedProfile,
) -> list[JobSearchResult]:
    role_catalog = [
        {
            "role": "Backend Engineer",
            "company": "Maple Stack",
            "description": "Build internal APIs, data services, and workflow automation for product teams.",
            "signals": ["python", "fastapi", "sql", "api", "backend"],
            "risks": ["May expect deeper database tuning experience."],
        },
        {
            "role": "AI Application Engineer",
            "company": "Northstar Agents",
            "description": "Ship agent workflows, prompt tooling, and retrieval-backed internal assistants.",
            "signals": ["llm", "rag", "agent", "evaluation", "prompt"],
            "risks": ["May expect hands-on evaluation and prompt iteration examples."],
        },
        {
            "role": "Data Engineer",
            "company": "Riverlane Metrics",
            "description": "Maintain ETL pipelines, analytics datasets, and platform data contracts.",
            "signals": ["sql", "python", "etl", "data", "warehouse"],
            "risks": ["May expect stronger pipeline orchestration evidence."],
        },
        {
            "role": "Embedded Software Engineer",
            "company": "Harbor Embedded",
            "description": "Develop firmware-adjacent services and device integration tooling.",
            "signals": ["stm32", "rtos", "embedded", "c++", "uart"],
            "risks": ["May expect hardware bring-up or board-level debugging examples."],
        },
        {
            "role": "Full Stack Developer",
            "company": "Cedar Product Studio",
            "description": "Deliver end-to-end product features across API and frontend surfaces.",
            "signals": ["vue", "typescript", "python", "api", "product"],
            "risks": ["Role may lean more frontend than the profile prefers."],
        },
        {
            "role": "Platform Engineer",
            "company": "Granite Cloud",
            "description": "Improve developer workflows, service deployment, and internal platform reliability.",
            "signals": ["docker", "ci", "testing", "platform", "python"],
            "risks": ["May expect production infrastructure ownership examples."],
        },
    ]
    normalized_keywords = _clean_list(
        keywords + confirmed_profile.core_skills + confirmed_profile.supporting_skills
    )
    normalized_roles = _clean_list(target_roles)
    derived_locations = locations or ["Remote", "Tokyo", "Shenzhen"]

    results: list[JobSearchResult] = []
    for index, item in enumerate(role_catalog):
        matched_keywords = [
            keyword
            for keyword in normalized_keywords
            if any(signal in keyword.lower() or keyword.lower() in signal for signal in item["signals"])
        ]
        role_match = any(
            item["role"].lower() in role.lower() or role.lower() in item["role"].lower()
            for role in normalized_roles
        )
        if role_match and item["role"] not in normalized_roles:
            matched_keywords = matched_keywords or [item["role"]]
        score = min(95, 60 + len(matched_keywords) * 5 + (10 if role_match else 0))
        match_reasons = []
        if role_match:
            match_reasons.append(f"Target role overlap with {item['role']}.")
        if matched_keywords:
            match_reasons.append("Matched keywords: " + ", ".join(matched_keywords[:4]) + ".")
        if confirmed_profile.work_arrangements:
            match_reasons.append("Can be filtered later by preferred work arrangements.")
        if not match_reasons:
            match_reasons.append("Broad software profile alignment from confirmed profile.")

        location = derived_locations[index % len(derived_locations)]
        result_id = str(uuid5(NAMESPACE_URL, f"{query}:{item['role']}:{item['company']}:{location}"))
        results.append(
            JobSearchResult(
                job_result_id=result_id,
                title=item["role"],
                company=item["company"],
                location=location,
                source="local_mock",
                source_provider="local_mock",
                source_url=None,
                raw_snippet=item["description"],
                description=item["description"],
                matched_keywords=matched_keywords[:6],
                match_reasons=match_reasons,
                risks=item["risks"],
                match_score=score,
                recommended_action="Review this role as a candidate for deeper application planning.",
                analysis_mode="mock",
                confidence_label=_confidence_label_for_score(score),
            )
        )

    results.sort(key=lambda item: item.match_score, reverse=True)
    return results[:6]


def _match_candidates(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    analyzed_items: list[dict[str, object]],
) -> list[dict[str, object]]:
    matched_items: list[dict[str, object]] = []
    for candidate_index, item in enumerate(analyzed_items):
        candidate = item["candidate"]
        analysis = item["analysis"]
        recall_scorecard = item.get("scorecard")
        enriched_candidate = _candidate_with_analysis(candidate, analysis)
        final_scorecard = build_candidate_scorecard(
            candidate_index,
            enriched_candidate,
            confirmed_profile=confirmed_profile,
            search_plan=search_plan,
        )
        recall_risks = (
            recall_scorecard.risks
            if isinstance(recall_scorecard, CandidateScorecard)
            else []
        )

        matched_items.append(
            {
                "candidate": candidate,
                "analysis": analysis,
                "analysis_mode": item["analysis_mode"],
                "recall_score": (
                    recall_scorecard.match_score
                    if isinstance(recall_scorecard, CandidateScorecard)
                    else None
                ),
                "match_score": final_scorecard.match_score,
                "score_breakdown": final_scorecard.score_breakdown,
                "evidence_quotes": final_scorecard.evidence_quotes,
                "matched_keywords": final_scorecard.matched_keywords[:6],
                "match_reasons": final_scorecard.match_reasons,
                "risks": _clean_list(
                    recall_risks
                    + final_scorecard.risks
                    + _metadata_risks(candidate, confirmed_profile)
                ),
                "confidence_label": final_scorecard.confidence_label,
            }
        )

    matched_items.sort(key=lambda item: int(item["match_score"]), reverse=True)
    return _diversify_matched_items(matched_items)


def _diversify_matched_items(
    matched_items: list[dict[str, object]],
    *,
    score_window: int = 5,
) -> list[dict[str, object]]:
    """Prefer new companies and sources only among candidates with close scores."""
    pending = list(enumerate(matched_items))
    diversified: list[tuple[int, dict[str, object]]] = []
    company_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    while pending:
        best_score = int(pending[0][1]["match_score"])
        window = [
            entry
            for entry in pending
            if int(entry[1]["match_score"]) >= best_score - score_window
        ]
        original_index, selected = min(
            window,
            key=lambda entry: (
                company_counts[_diversity_company_key(entry)],
                source_counts[_diversity_source_key(entry)],
                -int(entry[1]["match_score"]),
                entry[0],
            ),
        )
        pending.remove((original_index, selected))
        company_counts[_diversity_company_key((original_index, selected))] += 1
        source_counts[_diversity_source_key((original_index, selected))] += 1
        diversified.append((original_index, selected))

    for rank, (original_index, item) in enumerate(diversified):
        item["diversity_adjusted"] = rank != original_index
    return [item for _, item in diversified]


def _diversity_company_key(entry: tuple[int, dict[str, object]]) -> str:
    original_index, item = entry
    candidate = item["candidate"]
    company = str(getattr(candidate, "company", "") or "").strip().casefold()
    return company or f"missing-company:{original_index}"


def _diversity_source_key(entry: tuple[int, dict[str, object]]) -> str:
    original_index, item = entry
    candidate = item["candidate"]
    source = str(getattr(candidate, "source_provider", "") or "").strip().casefold()
    return source or f"missing-source:{original_index}"


def _candidate_with_analysis(candidate: RawJobCandidate, analysis: object) -> RawJobCandidate:
    evidence_sections = [
        getattr(analysis, "raw_jd", "") or "",
        *list(getattr(analysis, "responsibilities", []) or []),
        *list(getattr(analysis, "required_skills", []) or []),
        *list(getattr(analysis, "preferred_skills", []) or []),
        *list(getattr(analysis, "experience_requirements", []) or []),
        *list(getattr(analysis, "education_requirements", []) or []),
        *list(getattr(analysis, "keywords", []) or []),
    ]
    analysis_text = "\n".join(_clean_list(evidence_sections))
    return candidate.model_copy(
        update={
            "title": candidate.title or getattr(analysis, "job_title", None),
            "company": candidate.company or getattr(analysis, "company", None),
            "location": candidate.location or getattr(analysis, "location", None),
            "raw_description": analysis_text or candidate.raw_description,
        }
    )


def _assemble_results(
    matched_items: list[dict[str, object]],
    *,
    source: str,
) -> list[JobSearchResult]:
    results: list[JobSearchResult] = []
    seen_result_keys: set[str] = set()
    for item in matched_items:
        candidate = item["candidate"]
        result_key = candidate_recall_key(candidate)
        if result_key in seen_result_keys:
            continue
        seen_result_keys.add(result_key)
        analysis = item["analysis"]
        description = getattr(candidate, "snippet", None) or getattr(analysis, "raw_jd", "")
        source_url = getattr(candidate, "source_url", None)
        title = getattr(candidate, "title", None) or getattr(analysis, "job_title", None) or "Untitled role"
        company = getattr(candidate, "company", None) or getattr(analysis, "company", None) or "Unknown company"
        location = getattr(candidate, "location", None) or getattr(analysis, "location", None) or "Unspecified"
        result_id = str(uuid5(NAMESPACE_URL, f"{source}:{title}:{company}:{location}:{source_url or description}"))
        score = int(item["match_score"])
        results.append(
            JobSearchResult(
                job_result_id=result_id,
                title=title,
                company=company,
                location=location,
                source=source,
                source_provider=getattr(candidate, "source_provider", None),
                source_url=source_url,
                raw_snippet=getattr(candidate, "snippet", None),
                description=description,
                matched_keywords=list(item["matched_keywords"]),
                match_reasons=list(item["match_reasons"]),
                risks=list(item["risks"]),
                match_score=score,
                recall_score=item.get("recall_score"),
                final_match_score=score,
                score_breakdown=dict(item.get("score_breakdown", {})),
                evidence_quotes=list(item.get("evidence_quotes", [])),
                recommended_action=_recommended_action(score),
                analysis_mode=item["analysis_mode"],
                confidence_label=item["confidence_label"],
            )
        )
    return results


def _metadata_risks(candidate: object, confirmed_profile: ConfirmedProfile) -> list[str]:
    risks: list[str] = []
    if not getattr(candidate, "source_url", None):
        risks.append("Source URL is missing.")
    if getattr(candidate, "location", None) is None and confirmed_profile.preferred_locations:
        risks.append("Location metadata is incomplete.")
    for warning in getattr(candidate, "provider_warnings", []) or []:
        warning_text = str(warning)
        if _is_boilerplate_browser_helper_warning(warning_text):
            continue
        risks.append(warning_text)
    return risks


def _is_boilerplate_browser_helper_warning(warning: str) -> bool:
    normalized = warning.lower()
    return any(
        fragment in normalized
        for fragment in (
            "browser helper",
            "platform cookies",
            "local boss browser session",
            "cookies were not sent",
            "cookies are not stored",
        )
    )


def _confidence_label_for_score(score: int) -> str:
    if score >= 85:
        return "strong"
    if score >= 72:
        return "medium"
    if score >= 58:
        return "limited"
    return "weak"


def _recommended_action(score: int) -> str:
    if score >= 85:
        return "Prioritize this role for detailed review."
    if score >= 72:
        return "Worth reviewing closely before deciding whether to save."
    if score >= 58:
        return "Review the requirements carefully before investing more time."
    return "Keep as a lower-priority option unless the role is especially attractive."


def _source_provider_counts(results: list[JobSearchResult]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for result in results:
        counts[result.source_provider or result.source] += 1
    return dict(counts)


def _clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
