from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.prompts.loader import load_prompt
from app.schemas.profile_enrichment import (
    EvidenceBoundSuggestion,
    ResumeProfileEnrichmentResult,
    SectionEnrichmentDraft,
)
from app.schemas.profile_review import ResumeProfileReviewResult
from app.schemas.resume import EducationItem, ProjectExperience, WorkExperience
from app.services.llm_service import LLMService, LLMServiceError
from app.services.profile_enrichment_quality import validate_evidence_bound_suggestion
from app.services.resume_profile_review_service import build_resume_profile_review

PROFILE_ENRICHMENT_PROMPT_VERSION = "profile_enrichment_v1"
UNAVAILABLE_WARNING = (
    "LLM profile enrichment unavailable; using deterministic baseline only"
)


def build_resume_profile_enrichment(
    *,
    resume_text: str,
    target_roles: list[str] | None = None,
    use_llm: bool = False,
    llm_service: LLMService | None = None,
) -> ResumeProfileEnrichmentResult:
    baseline_review = build_resume_profile_review(resume_text, target_roles)
    normalized_target_roles = _normalize_list(target_roles)
    result = _baseline_result(baseline_review)
    if not use_llm:
        return result

    service = llm_service or LLMService()
    profile = baseline_review.parsed_profile
    raw_resume_text = resume_text.strip()
    suggestions: list[EvidenceBoundSuggestion] = []
    quality_warnings = list(result.quality_warnings)
    missing_questions = list(result.missing_info_questions)
    llm_success_count = 0
    fallback_count = 0
    discarded_count = 0

    items: list[tuple[str, int, Any]] = [
        *[("project", index, project) for index, project in enumerate(profile.projects)],
        *[
            ("work", index, work)
            for index, work in enumerate(profile.work_experiences)
        ],
        *[
            ("education", index, education)
            for index, education in enumerate(profile.education)
        ],
    ]

    for section, index, item in items:
        source_text = getattr(item, "raw_text", "") or ""
        if not source_text.strip():
            fallback_count += 1
            continue
        try:
            draft = _enrich_item(
                section=section,
                item=item,
                index=index,
                target_roles=normalized_target_roles,
                service=service,
            )
        except (LLMServiceError, ValidationError, ValueError, TypeError, KeyError):
            fallback_count += 1
            continue

        llm_success_count += 1
        missing_questions = _merge_unique(
            missing_questions,
            _normalize_list(draft.clarifying_questions),
        )
        for suggestion in draft.suggestions:
            grounded = validate_evidence_bound_suggestion(
                suggestion=suggestion,
                source_text=source_text,
                full_resume_text=raw_resume_text,
                known_skills=profile.skills,
            )
            if grounded is None:
                discarded_count += 1
                quality_warnings = _merge_unique(
                    quality_warnings,
                    ["discarded ungrounded profile enrichment suggestion"],
                )
                continue
            suggestions.append(grounded)

    if llm_success_count == 0 and items:
        quality_warnings = _merge_unique(quality_warnings, [UNAVAILABLE_WARNING])

    confidence_label = _enrichment_confidence_label(
        baseline_review.confidence_label,
        llm_success_count=llm_success_count,
        discarded_count=discarded_count,
    )
    return ResumeProfileEnrichmentResult(
        baseline_review=baseline_review,
        enrichment_suggestions=suggestions,
        quality_warnings=quality_warnings,
        missing_info_questions=missing_questions,
        llm_success_count=llm_success_count,
        fallback_count=fallback_count,
        discarded_suggestion_count=discarded_count,
        confidence_label=confidence_label,
    )


def _enrich_project_item(
    project: ProjectExperience,
    index: int,
    target_roles: list[str],
    *,
    service: LLMService,
) -> SectionEnrichmentDraft:
    return _enrich_item(
        section="project",
        item=project,
        index=index,
        target_roles=target_roles,
        service=service,
    )


def _enrich_work_item(
    work: WorkExperience,
    index: int,
    target_roles: list[str],
    *,
    service: LLMService,
) -> SectionEnrichmentDraft:
    return _enrich_item(
        section="work",
        item=work,
        index=index,
        target_roles=target_roles,
        service=service,
    )


def _enrich_education_item(
    education: EducationItem,
    index: int,
    *,
    service: LLMService,
) -> SectionEnrichmentDraft:
    return _enrich_item(
        section="education",
        item=education,
        index=index,
        target_roles=[],
        service=service,
    )


def _generate_contextual_missing_questions(
    baseline_review: ResumeProfileReviewResult,
    target_roles: list[str],
) -> list[str]:
    questions = list(baseline_review.missing_info_questions)
    if target_roles and not baseline_review.parsed_profile.highlights:
        questions.append(
            "Which quantified outcome best supports your target roles: "
            + ", ".join(target_roles)
            + "?"
        )
    return _merge_unique([], questions)


def _enrich_item(
    *,
    section: str,
    item: ProjectExperience | WorkExperience | EducationItem,
    index: int,
    target_roles: list[str],
    service: LLMService,
) -> SectionEnrichmentDraft:
    system_prompt = load_prompt(f"profile_enrichment/{section}_system.md")
    user_template = load_prompt(f"profile_enrichment/{section}_user_template.md")
    payload = service.chat_completion_json(
        system_prompt=system_prompt,
        user_prompt=user_template.format(
            section_type=section,
            item_index=index,
            item_raw_text=getattr(item, "raw_text", ""),
            existing_parsed_fields=json.dumps(
                item.model_dump(mode="json"),
                ensure_ascii=False,
            ),
            target_roles=json.dumps(target_roles, ensure_ascii=False),
            schema_hint=json.dumps(_schema_hint(), ensure_ascii=False),
        ),
    )
    normalized = dict(payload)
    normalized.setdefault("section", section)
    normalized.setdefault("item_index", index)
    return SectionEnrichmentDraft.model_validate(normalized)


def _baseline_result(
    baseline_review: ResumeProfileReviewResult,
) -> ResumeProfileEnrichmentResult:
    return ResumeProfileEnrichmentResult(
        baseline_review=baseline_review,
        enrichment_suggestions=[],
        quality_warnings=list(baseline_review.quality_warnings),
        missing_info_questions=list(baseline_review.missing_info_questions),
        llm_success_count=0,
        fallback_count=0,
        discarded_suggestion_count=0,
        confidence_label=baseline_review.confidence_label,
    )


def _schema_hint() -> dict[str, object]:
    return {
        "section": "project | work | education",
        "item_index": 0,
        "suggestions": [
            {
                "section": "project",
                "item_index": 0,
                "field": "description",
                "suggested_value": "evidence-bound suggestion",
                "source_quote": "exact quote copied from item_raw_text",
                "confidence_label": "medium",
                "warnings": [],
            }
        ],
        "clarifying_questions": ["question when evidence is missing"],
    }


def _enrichment_confidence_label(
    baseline_label: str,
    *,
    llm_success_count: int,
    discarded_count: int,
) -> str:
    if llm_success_count == 0:
        return baseline_label
    if discarded_count > llm_success_count:
        return "limited"
    return baseline_label if baseline_label in {"strong", "medium"} else "medium"


def _normalize_list(items: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for item in items or []:
        value = item.strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _merge_unique(existing: list[str], additions: list[str]) -> list[str]:
    merged = list(existing)
    seen = {item.lower() for item in merged}
    for item in additions:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged
