from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.schemas.confirmed_profile import ConfirmedProfileCreateRequest
from app.schemas.profile_enrichment import ResumeProfileEnrichmentResult
from app.schemas.profile_review import ConfirmedResumeProfileResult
from app.services.llm_service import LLMService, LLMServiceError
from app.services.resume_profile_enrichment_service import (
    build_resume_profile_enrichment,
)
from app.services.resume_profile_review_service import (
    confirm_resume_profile,
)
from app.services.errors import JobAgentError
from app.services.profile_review_state_helpers import (
    apply_suggestion_to_profile_draft,
    build_confirmed_profile_save_payload,
    build_confirm_user_edits_from_profile_draft,
    build_profile_draft_from_baseline,
)
from tests.fixtures.resumes.profile_review_quality_cases import (
    PROFILE_REVIEW_QUALITY_CASES,
    ProfileReviewQualityCase,
)

QUALITY_VERDICTS = {"strong", "acceptable", "needs_review", "failed"}


class ProfileReviewQualityCaseResult(BaseModel):
    case_id: str
    title: str
    target_roles: list[str] = Field(default_factory=list)
    baseline_confidence_label: str
    baseline_quality_warnings: list[str] = Field(default_factory=list)
    baseline_missing_info_questions: list[str] = Field(default_factory=list)
    parsed_skills: list[str] = Field(default_factory=list)
    parsed_project_count: int = 0
    parsed_work_experience_count: int = 0
    parsed_education_count: int = 0
    parsed_highlights: list[str] = Field(default_factory=list)
    profile_draft_summary: dict[str, Any] = Field(default_factory=dict)
    enrichment_enabled: bool
    enrichment_suggestion_count: int = 0
    enrichment_llm_success_count: int = 0
    enrichment_fallback_count: int = 0
    enrichment_discarded_suggestion_count: int = 0
    enrichment_quality_warnings: list[str] = Field(default_factory=list)
    accepted_suggestion_count: int = 0
    edited_suggestion_count: int = 0
    rejected_suggestion_count: int = 0
    confirmed_confidence_label: str
    confirmed_skill_count: int = 0
    confirmed_project_count: int = 0
    confirmed_work_experience_count: int = 0
    confirmed_remaining_warnings: list[str] = Field(default_factory=list)
    save_payload_ready: bool
    quality_verdict: str
    reviewer_notes: list[str] = Field(default_factory=list)
    save_payload_snapshot: dict[str, Any] | None = None


class ProfileReviewQualityComparison(BaseModel):
    case_id: str
    deterministic_verdict: str
    llm_enriched_verdict: str
    skill_count_delta: int
    suggestion_count: int
    warning_count_delta: int
    confirmed_confidence_delta: str | None = None
    improvement_summary: str
    risk_summary: str


class ProfileReviewQualitySuiteResult(BaseModel):
    mode: str
    total_cases: int
    strong_cases: int
    acceptable_cases: int
    needs_review_cases: int
    failed_cases: int
    cases: list[ProfileReviewQualityCaseResult] = Field(default_factory=list)


class ProfileReviewQualityRunOutputs(BaseModel):
    deterministic: ProfileReviewQualitySuiteResult | None = None
    llm_enriched: ProfileReviewQualitySuiteResult | None = None
    comparisons: list[ProfileReviewQualityComparison] = Field(default_factory=list)


class FakeProfileReviewLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raw_text = _extract_between(user_prompt, "item_raw_text:\n", "\n\nexisting parsed fields:")
        section = _extract_after(user_prompt, "section_type: ").splitlines()[0].strip()
        target_roles_text = _extract_between(user_prompt, "target_roles:\n", "\n\nrequired JSON schema hint:")

        raw_lower = raw_text.lower()
        if "95% validation accuracy" in raw_text:
            return {
                "section": section,
                "suggestions": [
                    {
                        "section": section,
                        "field": "highlights",
                        "suggested_value": ["95% validation accuracy"],
                        "source_quote": "95% validation accuracy",
                        "confidence_label": "medium",
                        "warnings": [],
                    },
                    {
                        "section": section,
                        "field": "description",
                        "suggested_value": "Improved latency by 50ms",
                        "source_quote": "95% validation accuracy",
                        "confidence_label": "medium",
                        "warnings": [],
                    },
                ],
                "clarifying_questions": [],
            }
        if "fastapi" in raw_lower and "streamlit" in raw_lower:
            return {
                "section": section,
                "suggestions": [
                    {
                        "section": section,
                        "field": "technologies",
                        "suggested_value": ["FastAPI", "Streamlit"],
                        "source_quote": "FastAPI and Streamlit",
                        "confidence_label": "medium",
                        "warnings": [],
                    },
                    {
                        "section": section,
                        "field": "description",
                        "suggested_value": "Designed profile review endpoints",
                        "source_quote": "Designed profile review endpoints",
                        "confidence_label": "medium",
                        "warnings": [],
                    },
                ],
                "clarifying_questions": [],
            }
        if "stm32" in raw_lower or "uart" in raw_lower or "usart" in raw_lower:
            return {
                "section": section,
                "suggestions": [
                    {
                        "section": section,
                        "field": "technologies",
                        "suggested_value": ["STM32", "USART"],
                        "source_quote": "STM32, ADC, PWM, GPIO, and USART",
                        "confidence_label": "medium",
                        "warnings": [],
                    }
                ],
                "clarifying_questions": [],
            }
        if "wind" in raw_lower or "crm" in raw_lower:
            return {
                "section": section,
                "suggestions": [
                    {
                        "section": section,
                        "field": "description",
                        "suggested_value": "Prepared CRM updates and competitor analysis summaries",
                        "source_quote": "Prepared CRM updates, meeting notes, and competitor analysis summaries",
                        "confidence_label": "medium",
                        "warnings": [],
                    }
                ],
                "clarifying_questions": [],
            }
        if "python" in raw_lower and "ai job" in raw_lower:
            return {
                "section": section,
                "suggestions": [],
                "clarifying_questions": [
                    "Which project best demonstrates your Python or AI experience?"
                ],
            }
        if "backend engineer" in target_roles_text.lower() and "python" in raw_lower:
            return {
                "section": section,
                "suggestions": [
                    {
                        "section": section,
                        "field": "skills",
                        "suggested_value": ["Python"],
                        "source_quote": "Python",
                        "confidence_label": "medium",
                        "warnings": [],
                    }
                ],
                "clarifying_questions": [],
            }
        return {
            "section": section,
            "suggestions": [],
            "clarifying_questions": [],
        }


def run_profile_review_quality_case(
    case: ProfileReviewQualityCase,
    *,
    use_llm_enrichment: bool = False,
    simulate_user_decisions: bool = True,
    llm_service: LLMService | None = None,
) -> ProfileReviewQualityCaseResult:
    from app.services.resume_profile_review_service import build_resume_profile_review

    baseline_review = build_resume_profile_review(
        case.resume_text,
        target_roles=case.target_roles,
    )
    profile_draft = build_profile_draft_from_baseline(
        baseline_review.model_dump(mode="json"),
        target_roles=case.target_roles,
    )

    enrichment_result: ResumeProfileEnrichmentResult | None = None
    accepted_suggestions: list[dict[str, Any]] = []
    edited_suggestions: list[dict[str, Any]] = []
    rejected_suggestions: list[dict[str, Any]] = []
    missing_info_answers: dict[str, str] = {}
    reviewer_notes: list[str] = []

    if use_llm_enrichment:
        enrichment_result = build_resume_profile_enrichment(
            resume_text=case.resume_text,
            target_roles=case.target_roles,
            use_llm=True,
            llm_service=llm_service or FakeProfileReviewLLMService(),  # type: ignore[arg-type]
        )

    if simulate_user_decisions and enrichment_result is not None:
        (
            profile_draft,
            accepted_suggestions,
            edited_suggestions,
            rejected_suggestions,
        ) = _simulate_suggestion_decisions(profile_draft, enrichment_result)
        reviewer_notes.extend(_decision_notes(accepted_suggestions, edited_suggestions, rejected_suggestions))

    for question in baseline_review.missing_info_questions:
        missing_info_answers[question] = _answer_missing_info_question(case, question)

    user_edits = build_confirm_user_edits_from_profile_draft(profile_draft)
    if missing_info_answers:
        user_edits.notes = _merge_notes_with_answers(user_edits.notes, missing_info_answers)

    confirmed_result = confirm_resume_profile(
        baseline_review.parsed_profile,
        user_edits,
    )
    save_payload = build_confirmed_profile_save_payload(
        resume_text=case.resume_text.strip(),
        baseline_review=baseline_review.model_dump(mode="json"),
        confirmed_profile_result=confirmed_result.model_dump(mode="json"),
        accepted_suggestions=accepted_suggestions,
        edited_suggestions=edited_suggestions,
        rejected_suggestions=rejected_suggestions,
        missing_info_answers=missing_info_answers,
        notes=user_edits.notes,
    )
    save_payload_ready = False
    if save_payload is not None:
        try:
            ConfirmedProfileCreateRequest.model_validate(save_payload)
            save_payload_ready = True
        except ValidationError as exc:
            reviewer_notes.append(f"save payload validation failed: {exc.errors()[0]['msg']}")

    reviewer_notes.extend(_baseline_notes(case, baseline_review.model_dump(mode="json")))
    if enrichment_result is not None:
        reviewer_notes.extend(_enrichment_notes(enrichment_result))

    quality_verdict = _quality_verdict(
        case=case,
        baseline_review=baseline_review.model_dump(mode="json"),
        confirmed_result=confirmed_result,
        save_payload_ready=save_payload_ready,
        enrichment_result=enrichment_result,
    )

    return ProfileReviewQualityCaseResult(
        case_id=case.case_id,
        title=case.title,
        target_roles=case.target_roles,
        baseline_confidence_label=baseline_review.confidence_label,
        baseline_quality_warnings=baseline_review.quality_warnings,
        baseline_missing_info_questions=baseline_review.missing_info_questions,
        parsed_skills=baseline_review.parsed_profile.skills,
        parsed_project_count=len(baseline_review.parsed_profile.projects),
        parsed_work_experience_count=len(baseline_review.parsed_profile.work_experiences),
        parsed_education_count=len(baseline_review.parsed_profile.education),
        parsed_highlights=baseline_review.parsed_profile.highlights,
        profile_draft_summary=_profile_draft_summary(profile_draft),
        enrichment_enabled=use_llm_enrichment,
        enrichment_suggestion_count=(
            len(enrichment_result.enrichment_suggestions) if enrichment_result else 0
        ),
        enrichment_llm_success_count=(
            enrichment_result.llm_success_count if enrichment_result else 0
        ),
        enrichment_fallback_count=(
            enrichment_result.fallback_count if enrichment_result else 0
        ),
        enrichment_discarded_suggestion_count=(
            enrichment_result.discarded_suggestion_count if enrichment_result else 0
        ),
        enrichment_quality_warnings=(
            enrichment_result.quality_warnings if enrichment_result else []
        ),
        accepted_suggestion_count=len(accepted_suggestions),
        edited_suggestion_count=len(edited_suggestions),
        rejected_suggestion_count=len(rejected_suggestions),
        confirmed_confidence_label=confirmed_result.confidence_label,
        confirmed_skill_count=len(confirmed_result.confirmed_profile.skills),
        confirmed_project_count=len(confirmed_result.confirmed_profile.projects),
        confirmed_work_experience_count=len(
            confirmed_result.confirmed_profile.work_experiences
        ),
        confirmed_remaining_warnings=confirmed_result.remaining_warnings,
        save_payload_ready=save_payload_ready,
        quality_verdict=quality_verdict,
        reviewer_notes=_dedupe(reviewer_notes),
        save_payload_snapshot=save_payload,
    )


def run_profile_review_quality_suite(
    *,
    use_llm_enrichment: bool = False,
    simulate_user_decisions: bool = True,
    llm_service: LLMService | None = None,
) -> ProfileReviewQualitySuiteResult:
    cases = [
        run_profile_review_quality_case(
            case,
            use_llm_enrichment=use_llm_enrichment,
            simulate_user_decisions=simulate_user_decisions,
            llm_service=llm_service,
        )
        for case in PROFILE_REVIEW_QUALITY_CASES
    ]
    return ProfileReviewQualitySuiteResult(
        mode="llm_enriched" if use_llm_enrichment else "deterministic_only",
        total_cases=len(cases),
        strong_cases=sum(1 for case in cases if case.quality_verdict == "strong"),
        acceptable_cases=sum(
            1 for case in cases if case.quality_verdict == "acceptable"
        ),
        needs_review_cases=sum(
            1 for case in cases if case.quality_verdict == "needs_review"
        ),
        failed_cases=sum(1 for case in cases if case.quality_verdict == "failed"),
        cases=cases,
    )


def compare_profile_review_quality_suites(
    deterministic: ProfileReviewQualitySuiteResult,
    llm_enriched: ProfileReviewQualitySuiteResult,
) -> list[ProfileReviewQualityComparison]:
    deterministic_map = {case.case_id: case for case in deterministic.cases}
    comparisons: list[ProfileReviewQualityComparison] = []
    for llm_case in llm_enriched.cases:
        base_case = deterministic_map[llm_case.case_id]
        comparisons.append(
            ProfileReviewQualityComparison(
                case_id=llm_case.case_id,
                deterministic_verdict=base_case.quality_verdict,
                llm_enriched_verdict=llm_case.quality_verdict,
                skill_count_delta=llm_case.confirmed_skill_count - base_case.confirmed_skill_count,
                suggestion_count=llm_case.enrichment_suggestion_count,
                warning_count_delta=(
                    len(llm_case.confirmed_remaining_warnings)
                    - len(base_case.confirmed_remaining_warnings)
                ),
                confirmed_confidence_delta=_confidence_delta(
                    base_case.confirmed_confidence_label,
                    llm_case.confirmed_confidence_label,
                ),
                improvement_summary=_improvement_summary(base_case, llm_case),
                risk_summary=_risk_summary(base_case, llm_case),
            )
        )
    return comparisons


def write_profile_review_quality_outputs(
    outputs: ProfileReviewQualityRunOutputs,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_dir = output_dir / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if outputs.deterministic is not None:
        written.extend(
            _write_suite_files(
                outputs.deterministic,
                output_dir / "deterministic_summary.json",
                output_dir / "deterministic_summary.md",
                case_dir,
            )
        )
    if outputs.llm_enriched is not None:
        written.extend(
            _write_suite_files(
                outputs.llm_enriched,
                output_dir / "llm_enriched_summary.json",
                output_dir / "llm_enriched_summary.md",
                case_dir,
            )
        )
    if outputs.comparisons:
        comparison_json = output_dir / "comparison_summary.json"
        comparison_md = output_dir / "comparison_summary.md"
        comparison_json.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in outputs.comparisons],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        comparison_md.write_text(
            _render_comparison_markdown(outputs.comparisons),
            encoding="utf-8",
        )
        written.extend([comparison_json, comparison_md])
    return written


def _write_suite_files(
    suite: ProfileReviewQualitySuiteResult,
    json_path: Path,
    md_path: Path,
    case_dir: Path,
) -> list[Path]:
    json_path.write_text(
        json.dumps(suite.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(_render_suite_markdown(suite), encoding="utf-8")
    written = [json_path, md_path]
    for case in suite.cases:
        case_json = case_dir / f"{case.case_id}.json"
        case_md = case_dir / f"{case.case_id}.md"
        case_json.write_text(
            json.dumps(case.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        case_md.write_text(_render_case_markdown(case), encoding="utf-8")
        written.extend([case_json, case_md])
    return written


def _simulate_suggestion_decisions(
    profile_draft: dict[str, Any],
    enrichment_result: ResumeProfileEnrichmentResult,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    draft = json.loads(json.dumps(profile_draft))
    accepted: list[dict[str, Any]] = []
    edited: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    edited_once = False

    for suggestion in enrichment_result.enrichment_suggestions:
        suggestion_dict = suggestion.model_dump(mode="json")
        if suggestion.warnings:
            rejected.append(suggestion_dict)
            continue
        if not edited_once and suggestion.field in {"description", "highlights"}:
            edited_once = True
            edited_value = suggestion.suggested_value
            if isinstance(edited_value, list):
                edited_value = [str(item).strip() for item in edited_value]
            else:
                edited_value = str(edited_value).strip()
            draft = apply_suggestion_to_profile_draft(
                draft,
                suggestion_dict,
                edited_value=edited_value,
            )
            suggestion_dict["edited_value"] = edited_value
            edited.append(suggestion_dict)
            continue
        draft = apply_suggestion_to_profile_draft(draft, suggestion_dict)
        accepted.append(suggestion_dict)
    return draft, accepted, edited, rejected


def _answer_missing_info_question(case: ProfileReviewQualityCase, question: str) -> str:
    question_lower = question.lower()
    if "target role" in question_lower:
        return ", ".join(case.target_roles) or "AI Engineer"
    if "project" in question_lower:
        return f"{case.title} strongest project is described in the resume and should be highlighted."
    if "work-like evidence" in question_lower:
        return f"{case.title} includes project or research evidence relevant to the target role."
    if "measurable outcomes" in question_lower:
        return "Please keep the existing measurable outcomes from the resume evidence."
    return f"Clarify {case.title} profile evidence for reviewer follow-up."


def _merge_notes_with_answers(
    notes: str | None,
    missing_info_answers: dict[str, str],
) -> str:
    entries = [f"{question}: {answer}" for question, answer in missing_info_answers.items()]
    merged = [item for item in [notes, *entries] if item]
    return "\n".join(merged)


def _baseline_notes(case: ProfileReviewQualityCase, baseline_review: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    parsed_profile = baseline_review["parsed_profile"]
    parsed_skill_set = {skill.lower() for skill in parsed_profile.get("skills", [])}
    missing_skills = [
        skill for skill in case.expected_skills if skill.lower() not in parsed_skill_set
    ]
    if missing_skills:
        notes.append(f"missing expected skills: {', '.join(missing_skills)}")
    for section in case.expected_sections:
        if section == "projects" and not parsed_profile.get("projects"):
            notes.append("expected projects section is sparse or missing")
        if section == "work_experiences" and not parsed_profile.get("work_experiences"):
            notes.append("expected work experience section is sparse or missing")
        if section == "education" and not parsed_profile.get("education"):
            notes.append("expected education section is sparse or missing")
        if section == "highlights" and not parsed_profile.get("highlights"):
            notes.append("expected highlights section is sparse or missing")
    return notes


def _enrichment_notes(enrichment_result: ResumeProfileEnrichmentResult) -> list[str]:
    notes: list[str] = []
    if enrichment_result.discarded_suggestion_count:
        notes.append(
            f"discarded {enrichment_result.discarded_suggestion_count} unsupported enrichment suggestions"
        )
    if enrichment_result.fallback_count:
        notes.append(f"fallback_count={enrichment_result.fallback_count}")
    return notes


def _quality_verdict(
    *,
    case: ProfileReviewQualityCase,
    baseline_review: dict[str, Any],
    confirmed_result: ConfirmedResumeProfileResult,
    save_payload_ready: bool,
    enrichment_result: ResumeProfileEnrichmentResult | None,
) -> str:
    if not save_payload_ready:
        return "failed"

    confirmed_profile = confirmed_result.confirmed_profile
    parsed_skills = {skill.lower() for skill in confirmed_profile.skills}
    expected_skills_found = sum(
        1 for skill in case.expected_skills if skill.lower() in parsed_skills
    )
    expected_skill_ratio = (
        expected_skills_found / len(case.expected_skills) if case.expected_skills else 1.0
    )
    warning_count = len(confirmed_result.remaining_warnings)

    if case.case_id == "weak_resume":
        if confirmed_result.confidence_label == "strong":
            return "failed"
        if warning_count >= 2:
            return "acceptable"
        return "needs_review"

    if expected_skill_ratio >= 0.75 and warning_count <= 1:
        return "strong"
    if expected_skill_ratio >= 0.5 and warning_count <= 3:
        return "acceptable"
    if (
        enrichment_result
        and len(enrichment_result.enrichment_suggestions) > 0
        and warning_count <= 4
    ):
        return "needs_review"
    return "failed"


def _profile_draft_summary(profile_draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_count": len(profile_draft.get("skills") or []),
        "project_count": len(profile_draft.get("projects") or []),
        "work_experience_count": len(profile_draft.get("work_experiences") or []),
        "education_count": len(profile_draft.get("education") or []),
        "highlight_count": len(profile_draft.get("highlights") or []),
        "target_roles": profile_draft.get("target_roles") or [],
    }


def _decision_notes(
    accepted: list[dict[str, Any]],
    edited: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    if accepted:
        notes.append(f"accepted {len(accepted)} grounded suggestions")
    if edited:
        notes.append(f"edited {len(edited)} suggestions before confirmation")
    if rejected:
        notes.append(f"rejected {len(rejected)} suggestions")
    return notes


def _confidence_delta(base: str, updated: str) -> str | None:
    if base == updated:
        return None
    return f"{base}->{updated}"


def _improvement_summary(
    base_case: ProfileReviewQualityCaseResult,
    llm_case: ProfileReviewQualityCaseResult,
) -> str:
    if llm_case.confirmed_skill_count > base_case.confirmed_skill_count:
        return "LLM path improved confirmed skill coverage."
    if llm_case.quality_verdict != base_case.quality_verdict:
        return "LLM path changed overall evaluation verdict."
    if llm_case.accepted_suggestion_count or llm_case.edited_suggestion_count:
        return "LLM path produced usable suggestion decisions without increasing confirmed coverage."
    return "No meaningful LLM improvement observed."


def _risk_summary(
    base_case: ProfileReviewQualityCaseResult,
    llm_case: ProfileReviewQualityCaseResult,
) -> str:
    risks: list[str] = []
    if llm_case.enrichment_discarded_suggestion_count:
        risks.append("unsupported suggestions were discarded by grounding checks")
    if len(llm_case.confirmed_remaining_warnings) > len(base_case.confirmed_remaining_warnings):
        risks.append("confirmed profile warnings increased after LLM enrichment")
    if llm_case.enrichment_fallback_count:
        risks.append("one or more item enrichments fell back")
    return "; ".join(risks) if risks else "No notable LLM-specific risk increase."


def _render_suite_markdown(result: ProfileReviewQualitySuiteResult) -> str:
    lines = [
        f"# {result.mode.replace('_', ' ').title()} Profile Review Quality Summary",
        "",
        "## Overall",
        f"- total_cases: {result.total_cases}",
        f"- strong_cases: {result.strong_cases}",
        f"- acceptable_cases: {result.acceptable_cases}",
        f"- needs_review_cases: {result.needs_review_cases}",
        f"- failed_cases: {result.failed_cases}",
        "",
        "## Case Table",
        "| case_id | verdict | baseline_confidence | confirmed_confidence | parsed_skills | suggestions | save_payload_ready |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.case_id} | {case.quality_verdict} | {case.baseline_confidence_label} | "
            f"{case.confirmed_confidence_label} | {len(case.parsed_skills)} | "
            f"{case.enrichment_suggestion_count} | {case.save_payload_ready} |"
        )
    return "\n".join(lines) + "\n"


def _render_case_markdown(case: ProfileReviewQualityCaseResult) -> str:
    lines = [
        f"# {case.title}",
        "",
        "## Resume summary",
        f"- case_id: {case.case_id}",
        f"- target_roles: {', '.join(case.target_roles) or '-'}",
        "",
        "## Baseline parsed result",
        f"- baseline_confidence_label: {case.baseline_confidence_label}",
        f"- baseline_quality_warnings: {_format_list(case.baseline_quality_warnings)}",
        f"- baseline_missing_info_questions: {_format_list(case.baseline_missing_info_questions)}",
        f"- parsed_skills: {_format_list(case.parsed_skills)}",
        f"- parsed_project_count: {case.parsed_project_count}",
        f"- parsed_work_experience_count: {case.parsed_work_experience_count}",
        f"- parsed_education_count: {case.parsed_education_count}",
        f"- parsed_highlights: {_format_list(case.parsed_highlights)}",
        "",
        "## Profile draft summary",
        f"- draft: {json.dumps(case.profile_draft_summary, ensure_ascii=False)}",
        "",
        "## LLM enrichment result",
        f"- enrichment_enabled: {case.enrichment_enabled}",
        f"- enrichment_suggestion_count: {case.enrichment_suggestion_count}",
        f"- enrichment_llm_success_count: {case.enrichment_llm_success_count}",
        f"- enrichment_fallback_count: {case.enrichment_fallback_count}",
        f"- enrichment_discarded_suggestion_count: {case.enrichment_discarded_suggestion_count}",
        f"- enrichment_quality_warnings: {_format_list(case.enrichment_quality_warnings)}",
        "",
        "## Simulated user decisions",
        f"- accepted_suggestion_count: {case.accepted_suggestion_count}",
        f"- edited_suggestion_count: {case.edited_suggestion_count}",
        f"- rejected_suggestion_count: {case.rejected_suggestion_count}",
        "",
        "## Confirmed profile result",
        f"- confirmed_confidence_label: {case.confirmed_confidence_label}",
        f"- confirmed_skill_count: {case.confirmed_skill_count}",
        f"- confirmed_project_count: {case.confirmed_project_count}",
        f"- confirmed_work_experience_count: {case.confirmed_work_experience_count}",
        f"- confirmed_remaining_warnings: {_format_list(case.confirmed_remaining_warnings)}",
        "",
        "## Save payload readiness",
        f"- save_payload_ready: {case.save_payload_ready}",
        "",
        "## Quality verdict",
        f"- quality_verdict: {case.quality_verdict}",
        "",
        "## Reviewer notes",
    ]
    if case.reviewer_notes:
        lines.extend(f"- {item}" for item in case.reviewer_notes)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _render_comparison_markdown(comparisons: list[ProfileReviewQualityComparison]) -> str:
    lines = [
        "# Profile Review Quality Comparison",
        "",
        "case_id | deterministic verdict | llm verdict | improvement | risk | final recommendation",
        "--- | --- | --- | --- | --- | ---",
    ]
    for item in comparisons:
        final_recommendation = (
            "prefer llm-enriched review"
            if item.llm_enriched_verdict in {"strong", "acceptable"}
            and item.llm_enriched_verdict != item.deterministic_verdict
            else "keep deterministic as default review baseline"
        )
        lines.append(
            f"{item.case_id} | {item.deterministic_verdict} | {item.llm_enriched_verdict} | "
            f"{item.improvement_summary} | {item.risk_summary} | {final_recommendation}"
        )
    return "\n".join(lines) + "\n"


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
    return result


def _format_list(items: list[str]) -> str:
    return ", ".join(items) if items else "-"


def _extract_between(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return ""
    return text[start_index + len(start) : end_index].strip()


def _extract_after(text: str, start: str) -> str:
    start_index = text.find(start)
    if start_index == -1:
        return ""
    return text[start_index + len(start) :]
