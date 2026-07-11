from __future__ import annotations

from collections import Counter
from uuid import NAMESPACE_URL, uuid5

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import JobSearchResult
from app.services.job_candidate_filter import CandidateScorecard
from app.services.job_search_planner import JobSearchPlan
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
                recommended_action="Review fit, then tailor resume bullets before applying.",
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
    profile_terms = _clean_list(
        confirmed_profile.target_roles
        + confirmed_profile.search_keywords
        + confirmed_profile.core_skills
        + confirmed_profile.supporting_skills
        + search_plan.must_have_signals
    )
    target_roles = [item.lower() for item in _clean_list(confirmed_profile.target_roles + search_plan.target_roles)]

    matched_items: list[dict[str, object]] = []
    for item in analyzed_items:
        candidate = item["candidate"]
        analysis = item["analysis"]
        scorecard = item.get("scorecard")
        if isinstance(scorecard, CandidateScorecard):
            matched_items.append(
                {
                    "candidate": candidate,
                    "analysis": analysis,
                    "analysis_mode": item["analysis_mode"],
                    "match_score": scorecard.match_score,
                    "score_breakdown": scorecard.score_breakdown,
                    "evidence_quotes": scorecard.evidence_quotes,
                    "matched_keywords": scorecard.matched_keywords[:6],
                    "match_reasons": (
                        scorecard.match_reasons
                        or ["Candidate was selected by the shared LLM scoring rubric."]
                    ),
                    "risks": _clean_list(scorecard.risks + _metadata_risks(candidate, confirmed_profile)),
                    "confidence_label": scorecard.confidence_label,
                }
            )
            continue
        text_parts = [
            getattr(candidate, "title", "") or "",
            getattr(candidate, "company", "") or "",
            getattr(candidate, "location", "") or "",
            getattr(candidate, "snippet", "") or "",
            getattr(analysis, "raw_jd", "") or "",
            " ".join(getattr(analysis, "keywords", []) or []),
            " ".join(getattr(analysis, "required_skills", []) or []),
            " ".join(getattr(analysis, "preferred_skills", []) or []),
        ]
        combined_text = " ".join(text_parts).lower()
        matched_keywords = [term for term in profile_terms if term.lower() in combined_text]
        role_overlap = any(role in combined_text for role in target_roles)
        required_skill_count = len(set(matched_keywords))
        score = min(98, 45 + required_skill_count * 7 + (15 if role_overlap else 0))
        risks = []
        if not getattr(candidate, "source_url", None):
            risks.append("Source URL is missing.")
        if not matched_keywords:
            risks.append("Limited explicit keyword overlap with the confirmed profile.")
        if getattr(candidate, "location", None) is None and confirmed_profile.preferred_locations:
            risks.append("Location metadata is incomplete.")

        match_reasons = []
        if role_overlap:
            match_reasons.append("Target role language overlaps with the confirmed profile.")
        if matched_keywords:
            match_reasons.append("Matched profile signals: " + ", ".join(matched_keywords[:5]) + ".")
        if not match_reasons:
            match_reasons.append("Candidate remains in scope based on broad search-plan alignment.")

        matched_items.append(
            {
                "candidate": candidate,
                "analysis": analysis,
                "analysis_mode": item["analysis_mode"],
                "match_score": score,
                "score_breakdown": {},
                "evidence_quotes": [],
                "matched_keywords": matched_keywords[:6],
                "match_reasons": match_reasons,
                "risks": _clean_list(risks),
                "confidence_label": _confidence_label_for_score(score),
            }
        )

    matched_items.sort(key=lambda item: int(item["match_score"]), reverse=True)
    return matched_items


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
        return "Prioritize this role and tailor resume bullets before applying."
    if score >= 72:
        return "Worth reviewing closely and tailoring before applying."
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
