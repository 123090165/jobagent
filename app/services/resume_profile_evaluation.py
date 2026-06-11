from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.resume_profile_review_service import build_resume_profile_review


class ResumeProfileExpectedSignals(BaseModel):
    skills_any: list[str] = Field(default_factory=list)
    skills_all: list[str] = Field(default_factory=list)
    project_min_count: int = 0
    work_experience_min_count: int = 0
    education_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    expected_warning_keywords: list[str] = Field(default_factory=list)
    allowed_confidence_labels: list[str] = Field(default_factory=list)


class ResumeProfileCaseEvaluation(BaseModel):
    case_id: str
    title: str
    confidence_label: str
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    skill_hits: list[str] = Field(default_factory=list)
    missing_expected_skills: list[str] = Field(default_factory=list)
    project_count: int
    work_experience_count: int
    education_count: int
    highlight_count: int
    overall_label: str


class ResumeProfileEvaluationSuiteResult(BaseModel):
    total_cases: int
    strong_cases: int
    medium_cases: int
    limited_cases: int
    weak_cases: int
    cases: list[ResumeProfileCaseEvaluation] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)


def evaluate_profile_review_case(
    *,
    case_id: str,
    title: str,
    resume_text: str,
    target_roles: list[str],
    expected: ResumeProfileExpectedSignals,
    known_limitations: list[str] | None = None,
) -> ResumeProfileCaseEvaluation:
    review = build_resume_profile_review(resume_text, target_roles=target_roles)
    profile = review.parsed_profile
    profile_text = _join_profile_text(
        profile.raw_text,
        *profile.skills,
        *(project.raw_text for project in profile.projects),
        *(project.description for project in profile.projects),
        *(highlight for project in profile.projects for highlight in project.highlights),
        *(work.raw_text for work in profile.work_experiences),
        *(education.raw_text for education in profile.education),
        *profile.highlights,
    )

    skill_hits = _matched_terms(profile.skills, expected.skills_any + expected.skills_all)
    missing_expected_skills = [
        skill for skill in expected.skills_all if not _contains_term(profile.skills, skill)
    ]

    passed_checks: list[str] = []
    failed_checks: list[str] = []

    _record(
        passed_checks,
        failed_checks,
        "skills_any_match",
        not expected.skills_any or bool(_matched_terms(profile.skills, expected.skills_any)),
    )
    _record(
        passed_checks,
        failed_checks,
        "skills_all_match",
        not missing_expected_skills,
    )
    _record(
        passed_checks,
        failed_checks,
        "project_count_min",
        len(profile.projects) >= expected.project_min_count,
    )
    _record(
        passed_checks,
        failed_checks,
        "work_experience_count_min",
        len(profile.work_experiences) >= expected.work_experience_min_count,
    )
    _record(
        passed_checks,
        failed_checks,
        "education_keyword_match",
        not expected.education_keywords
        or any(_contains_text(profile_text, keyword) for keyword in expected.education_keywords),
    )
    _record(
        passed_checks,
        failed_checks,
        "highlight_keyword_match",
        not expected.highlight_keywords
        or any(_contains_text(profile_text, keyword) for keyword in expected.highlight_keywords),
    )
    warning_text = _join_profile_text(*review.quality_warnings)
    _record(
        passed_checks,
        failed_checks,
        "expected_warning_match",
        not expected.expected_warning_keywords
        or any(
            _contains_text(warning_text, keyword)
            for keyword in expected.expected_warning_keywords
        ),
    )
    _record(
        passed_checks,
        failed_checks,
        "confidence_label_allowed",
        not expected.allowed_confidence_labels
        or review.confidence_label in expected.allowed_confidence_labels,
    )
    _record(
        passed_checks,
        failed_checks,
        "missing_info_questions_present_when_warnings_exist",
        not review.quality_warnings or bool(review.missing_info_questions),
    )

    return ResumeProfileCaseEvaluation(
        case_id=case_id,
        title=title,
        confidence_label=review.confidence_label,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        warnings=review.quality_warnings,
        missing_info_questions=review.missing_info_questions,
        skill_hits=skill_hits,
        missing_expected_skills=missing_expected_skills,
        project_count=len(profile.projects),
        work_experience_count=len(profile.work_experiences),
        education_count=len(profile.education),
        highlight_count=len(profile.highlights),
        overall_label=_overall_label(failed_checks),
    )


def evaluate_profile_review_suite(
    cases: list[dict],
) -> ResumeProfileEvaluationSuiteResult:
    evaluations: list[ResumeProfileCaseEvaluation] = []
    limitations: list[str] = []
    for case in cases:
        expected = ResumeProfileExpectedSignals(**case["expected"])
        evaluations.append(
            evaluate_profile_review_case(
                case_id=case["case_id"],
                title=case["title"],
                resume_text=case["resume_text"],
                target_roles=case.get("target_roles", []),
                expected=expected,
                known_limitations=case.get("known_limitations"),
            )
        )
        limitations.extend(case.get("known_limitations") or [])

    return ResumeProfileEvaluationSuiteResult(
        total_cases=len(evaluations),
        strong_cases=_count_label(evaluations, "strong"),
        medium_cases=_count_label(evaluations, "medium"),
        limited_cases=_count_label(evaluations, "limited"),
        weak_cases=_count_label(evaluations, "weak"),
        cases=evaluations,
        known_limitations=_dedupe(limitations),
    )


def _record(
    passed_checks: list[str],
    failed_checks: list[str],
    check_name: str,
    condition: bool,
) -> None:
    if condition:
        passed_checks.append(check_name)
    else:
        failed_checks.append(check_name)


def _overall_label(failed_checks: list[str]) -> str:
    if not failed_checks:
        return "strong"
    if len(failed_checks) <= 2:
        return "medium"
    if len(failed_checks) <= 4:
        return "limited"
    return "weak"


def _count_label(cases: list[ResumeProfileCaseEvaluation], label: str) -> int:
    return sum(1 for case in cases if case.overall_label == label)


def _matched_terms(values: list[str], expected_terms: list[str]) -> list[str]:
    return _dedupe([
        term
        for term in expected_terms
        if _contains_term(values, term)
    ])


def _contains_term(values: list[str], term: str) -> bool:
    return any(_contains_text(value, term) for value in values)


def _contains_text(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def _join_profile_text(*items: str | None) -> str:
    return "\n".join(item for item in items if item)


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
