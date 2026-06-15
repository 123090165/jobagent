from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.resume_profile_review_service import build_resume_profile_review
from app.services.search_ready_profile_builder import build_search_ready_profile
from tests.fixtures.resumes.profile_review_quality_cases import PROFILE_REVIEW_QUALITY_CASES


DEFAULT_OUTPUT_DIR = Path("docs/demo_outputs/search_ready_profile_eval")


class SearchReadyProfileCaseResult(BaseModel):
    case_id: str
    target_roles: list[str] = Field(default_factory=list)
    summary: str
    target_directions: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    auxiliary_skills: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    company_preferences: list[str] = Field(default_factory=list)
    profile_notes: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    quality_verdict: str


class SearchReadyProfileEvaluationSummary(BaseModel):
    total_cases: int
    strong_cases: int
    acceptable_cases: int
    needs_review_cases: int
    failed_cases: int
    cases: list[SearchReadyProfileCaseResult] = Field(default_factory=list)


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> SearchReadyProfileEvaluationSummary:
    cases: list[SearchReadyProfileCaseResult] = []
    for case in PROFILE_REVIEW_QUALITY_CASES:
        review = build_resume_profile_review(case.resume_text, target_roles=case.target_roles)
        search_ready = build_search_ready_profile(
            review.parsed_profile,
            case.target_roles,
            quality_warnings=review.quality_warnings,
            missing_info_questions=review.missing_info_questions,
            source_profile_snapshot=review.model_dump(mode="json"),
        )
        coverage_notes, quality_verdict = _evaluate_case(case, search_ready.model_dump(mode="json"))
        cases.append(
            SearchReadyProfileCaseResult(
                case_id=case.case_id,
                target_roles=case.target_roles,
                summary=search_ready.summary,
                target_directions=search_ready.target_directions,
                core_skills=search_ready.core_skills,
                auxiliary_skills=search_ready.auxiliary_skills,
                search_keywords=search_ready.search_keywords,
                preferred_locations=search_ready.preferred_locations,
                work_arrangements=search_ready.work_arrangements,
                company_preferences=search_ready.company_preferences,
                profile_notes=search_ready.profile_notes,
                quality_warnings=search_ready.quality_warnings,
                missing_info_questions=search_ready.missing_info_questions,
                coverage_notes=coverage_notes,
                quality_verdict=quality_verdict,
            )
        )

    summary = SearchReadyProfileEvaluationSummary(
        total_cases=len(cases),
        strong_cases=sum(1 for case in cases if case.quality_verdict == "strong"),
        acceptable_cases=sum(1 for case in cases if case.quality_verdict == "acceptable"),
        needs_review_cases=sum(1 for case in cases if case.quality_verdict == "needs_review"),
        failed_cases=sum(1 for case in cases if case.quality_verdict == "failed"),
        cases=cases,
    )
    _write_outputs(summary, output_dir)
    return summary


def _evaluate_case(case, profile: dict[str, object]) -> tuple[list[str], str]:
    coverage_notes: list[str] = []
    combined = _combined_terms(profile)
    combined_text = "\n".join(sorted(combined))
    target_directions = [item.lower() for item in profile["target_directions"]]
    expected_roles = [item.lower() for item in case.target_roles]
    role_hits = sum(1 for item in expected_roles if item in target_directions)
    focus_hits = sum(1 for item in case.expected_focus if item.lower() in combined_text)

    if case.case_id == "weak_resume":
        if "strong" in str(profile.get("summary", "")).lower():
            return ["weak profile should not be summarized as strong"], "failed"
        if profile["missing_info_questions"]:
            return ["missing info questions preserved for weak profile"], "acceptable"
        return ["weak profile lost missing info questions"], "needs_review"

    if role_hits < len(expected_roles):
        coverage_notes.append("not all target roles were preserved")
    if focus_hits < max(2, len(case.expected_focus) // 2):
        coverage_notes.append("focus coverage is thinner than expected")
    if len(set(profile["core_skills"]).intersection(set(profile["auxiliary_skills"]))) > 0:
        coverage_notes.append("core_skills and auxiliary_skills overlap")

    if case.case_id == "anker_ai_health_algorithm":
        if not all(
            term.lower() in combined_text
            for term in [
                "physiological signal processing",
                "ppg",
                "ecg",
                "acc",
                "wearable health monitoring",
            ]
        ):
            coverage_notes.append("AI health coverage is incomplete")
    if case.case_id == "realistic_business_resume_unstructured":
        if not any(term.lower() in combined_text for term in ["industry research", "market research"]):
            coverage_notes.append("business research coverage is incomplete")
        if "crm" not in combined_text or "wind" not in combined_text:
            coverage_notes.append("business tool coverage is incomplete")
    if case.case_id == "ai_agent_backend":
        for term in ["fastapi", "ai agent", "backend api", "evaluation / testing"]:
            if term not in combined_text:
                coverage_notes.append(f"missing agent/backend term: {term}")

    if not coverage_notes and focus_hits >= max(2, len(case.expected_focus) // 2):
        return ["search-ready profile coverage is strong"], "strong"
    if focus_hits >= max(1, len(case.expected_focus) // 3) and role_hits >= max(1, len(expected_roles)):
        return coverage_notes or ["search-ready profile is acceptable"], "acceptable"
    if focus_hits >= 1:
        return coverage_notes or ["search-ready profile still needs review"], "needs_review"
    return coverage_notes or ["search-ready profile failed expected coverage"], "failed"


def _combined_terms(profile: dict[str, object]) -> set[str]:
    combined: set[str] = set()
    for key in [
        "target_directions",
        "core_skills",
        "auxiliary_skills",
        "search_keywords",
        "preferred_locations",
        "work_arrangements",
        "company_preferences",
        "profile_notes",
    ]:
        value = profile.get(key, [])
        if isinstance(value, list):
            combined.update(str(item).lower() for item in value)
    combined.add(str(profile.get("summary", "")).lower())
    return combined


def _write_outputs(summary: SearchReadyProfileEvaluationSummary, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_dir = output_dir / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "summary.json").write_text(
        json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(_render_summary_markdown(summary), encoding="utf-8")

    for case in summary.cases:
        (case_dir / f"{case.case_id}.json").write_text(
            json.dumps(case.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (case_dir / f"{case.case_id}.md").write_text(
            _render_case_markdown(case),
            encoding="utf-8",
        )


def _render_summary_markdown(summary: SearchReadyProfileEvaluationSummary) -> str:
    lines = [
        "# Search-Ready Profile Evaluation Summary",
        "",
        f"- total_cases: {summary.total_cases}",
        f"- strong_cases: {summary.strong_cases}",
        f"- acceptable_cases: {summary.acceptable_cases}",
        f"- needs_review_cases: {summary.needs_review_cases}",
        f"- failed_cases: {summary.failed_cases}",
        "",
        "## Case Table",
        "| case_id | verdict | target_directions | core_skills | locations |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for case in summary.cases:
        lines.append(
            f"| {case.case_id} | {case.quality_verdict} | {len(case.target_directions)} | {len(case.core_skills)} | "
            f"{', '.join(case.preferred_locations) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def _render_case_markdown(case: SearchReadyProfileCaseResult) -> str:
    lines = [
        f"# {case.case_id}",
        "",
        f"- target_roles: {', '.join(case.target_roles) or '-'}",
        f"- summary: {case.summary}",
        f"- target_directions: {', '.join(case.target_directions) or '-'}",
        f"- core_skills: {', '.join(case.core_skills) or '-'}",
        f"- auxiliary_skills: {', '.join(case.auxiliary_skills) or '-'}",
        f"- search_keywords: {', '.join(case.search_keywords) or '-'}",
        f"- preferred_locations: {', '.join(case.preferred_locations) or '-'}",
        f"- work_arrangements: {', '.join(case.work_arrangements) or '-'}",
        f"- company_preferences: {', '.join(case.company_preferences) or '-'}",
        f"- profile_notes: {', '.join(case.profile_notes) or '-'}",
        f"- quality_warnings: {', '.join(case.quality_warnings) or '-'}",
        f"- missing_info_questions: {', '.join(case.missing_info_questions) or '-'}",
        f"- coverage_notes: {', '.join(case.coverage_notes) or '-'}",
        f"- quality_verdict: {case.quality_verdict}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    output_dir = DEFAULT_OUTPUT_DIR
    if len(sys.argv) > 2 and sys.argv[1] == "--output-dir":
        output_dir = Path(sys.argv[2])
    summary = run(output_dir)
    print(
        json.dumps(
            {
                "total_cases": summary.total_cases,
                "strong_cases": summary.strong_cases,
                "acceptable_cases": summary.acceptable_cases,
                "needs_review_cases": summary.needs_review_cases,
                "failed_cases": summary.failed_cases,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
