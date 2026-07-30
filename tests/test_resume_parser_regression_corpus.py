"""回归验证resume parser regression corpus的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import pytest

from app.schemas.resume import ResumeProfile
from app.services.resume_profile_review_service import build_resume_profile_review
from tests.fixtures.resumes.profile_review_quality_cases import (
    PROFILE_REVIEW_QUALITY_CASES,
    ProfileReviewQualityCase,
)


@pytest.mark.parametrize(
    "case",
    PROFILE_REVIEW_QUALITY_CASES,
    ids=[case.case_id for case in PROFILE_REVIEW_QUALITY_CASES],
)
def test_resume_quality_case_regression_baseline(case: ProfileReviewQualityCase) -> None:
    result = build_resume_profile_review(case.resume_text, case.target_roles)
    profile = result.parsed_profile

    assert result.analysis_mode == "deterministic"
    assert_no_fabricated_project(profile)
    assert_no_fabricated_work_experience(profile)
    assert_no_target_role_line_as_work_experience(profile)
    assert_skills_include(profile, case.regression_skills)
    assert_project_contains(profile, case.regression_project_keywords)
    assert_work_contains(profile, case.regression_work_keywords)
    assert_education_contains(profile, case.regression_education_keywords)
    assert_missing_info_contains(profile, case.regression_missing_info)


def test_weak_resume_regression_keeps_evidence_empty_and_missing_info_explicit() -> None:
    case = _case("weak_resume")
    result = build_resume_profile_review(case.resume_text, case.target_roles)
    profile = result.parsed_profile

    assert profile.skills == ["Python"]
    assert profile.projects == []
    assert profile.work_experiences == []
    assert_missing_info_contains(
        profile,
        ["project evidence", "work experience", "measurable outcomes"],
    )
    assert "resume profile has no project evidence" in result.quality_warnings
    assert "resume profile has no work experience evidence" in result.quality_warnings


def assert_skills_include(profile: ResumeProfile, expected_skills: list[str]) -> None:
    """提供 assert_skills_include 所需的测试行为。"""
    parsed_skills = {skill.lower() for skill in profile.skills}
    missing = [skill for skill in expected_skills if skill.lower() not in parsed_skills]
    assert not missing, f"missing expected skills: {missing}; parsed={profile.skills}"


def assert_no_fabricated_project(profile: ResumeProfile) -> None:
    """提供 assert_no_fabricated_project 所需的测试行为。"""
    project_names = [(project.name or "").strip() for project in profile.projects]
    assert "General project" not in project_names


def assert_no_fabricated_work_experience(profile: ResumeProfile) -> None:
    """提供 assert_no_fabricated_work_experience 所需的测试行为。"""
    raw_prefix = profile.raw_text.strip()[:160]
    fabricated = [
        work.raw_text
        for work in profile.work_experiences
        if work.raw_text.strip() == raw_prefix
    ]
    assert not fabricated, f"work experience appears fabricated from resume prefix: {fabricated}"


def assert_no_target_role_line_as_work_experience(profile: ResumeProfile) -> None:
    """提供 assert_no_target_role_line_as_work_experience 所需的测试行为。"""
    target_role_prefixes = (
        "target role",
        "target roles",
        "target direction",
        "target directions",
        "desired role",
        "desired roles",
        "目标方向",
        "目标岗位",
        "求职方向",
        "求职目标",
    )
    offending = [
        work.raw_text
        for work in profile.work_experiences
        if work.raw_text.strip().lower().startswith(target_role_prefixes)
    ]
    assert not offending, f"target role lines parsed as work experience: {offending}"


def assert_project_contains(profile: ResumeProfile, expected_keywords: list[str]) -> None:
    """提供 assert_project_contains 所需的测试行为。"""
    assert_keywords_in_text(
        " ".join(
            " ".join(
                part
                for part in [
                    project.name or "",
                    project.description,
                    project.raw_text,
                    *project.highlights,
                ]
                if part
            )
            for project in profile.projects
        ),
        expected_keywords,
        "projects",
    )


def assert_work_contains(profile: ResumeProfile, expected_keywords: list[str]) -> None:
    """提供 assert_work_contains 所需的测试行为。"""
    assert_keywords_in_text(
        " ".join(
            " ".join(
                part
                for part in [
                    work.company or "",
                    work.role or "",
                    work.description,
                    work.raw_text,
                ]
                if part
            )
            for work in profile.work_experiences
        ),
        expected_keywords,
        "work_experiences",
    )


def assert_education_contains(profile: ResumeProfile, expected_keywords: list[str]) -> None:
    """提供 assert_education_contains 所需的测试行为。"""
    assert_keywords_in_text(
        " ".join(
            " ".join(
                part
                for part in [
                    education.school or "",
                    education.degree or "",
                    education.major or "",
                    education.raw_text,
                ]
                if part
            )
            for education in profile.education
        ),
        expected_keywords,
        "education",
    )


def assert_missing_info_contains(profile: ResumeProfile, expected_items: list[str]) -> None:
    """提供 assert_missing_info_contains 所需的测试行为。"""
    parsed_missing_info = {item.lower() for item in profile.missing_info}
    missing = [
        item for item in expected_items if item.lower() not in parsed_missing_info
    ]
    assert not missing, (
        f"missing expected missing_info items: {missing}; "
        f"parsed={profile.missing_info}"
    )


def assert_keywords_in_text(text: str, expected_keywords: list[str], label: str) -> None:
    """提供 assert_keywords_in_text 所需的测试行为。"""
    lowered = text.lower()
    missing = [keyword for keyword in expected_keywords if keyword.lower() not in lowered]
    assert not missing, f"missing expected {label} keywords: {missing}; text={text}"


def _case(case_id: str) -> ProfileReviewQualityCase:
    for case in PROFILE_REVIEW_QUALITY_CASES:
        if case.case_id == case_id:
            return case
    raise AssertionError(f"unknown quality case: {case_id}")


# TODO(v4.6.3): add stricter assertions for exact multi-line project grouping,
# unstructured Chinese work/project boundaries, and internship availability lines
# once deterministic parser hardening begins.
