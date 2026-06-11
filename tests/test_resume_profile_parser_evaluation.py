from __future__ import annotations

from scripts.run_resume_profile_parser_evaluation import run
from app.services.resume_profile_evaluation import (
    ResumeProfileExpectedSignals,
    evaluate_profile_review_case,
    evaluate_profile_review_suite,
)
from tests.fixtures.resumes.profile_cases import PROFILE_EVALUATION_CASES


def _case(case_id: str) -> dict:
    return next(case for case in PROFILE_EVALUATION_CASES if case["case_id"] == case_id)


def test_evaluation_suite_can_run() -> None:
    result = evaluate_profile_review_suite(PROFILE_EVALUATION_CASES)

    assert result.total_cases >= 5
    assert len(result.cases) == result.total_cases


def test_weak_resume_produces_weak_or_limited_result() -> None:
    case = _case("weak_resume_sparse")
    result = evaluate_profile_review_case(
        case_id=case["case_id"],
        title=case["title"],
        resume_text=case["resume_text"],
        target_roles=case["target_roles"],
        expected=ResumeProfileExpectedSignals(**case["expected"]),
        known_limitations=case["known_limitations"],
    )

    assert result.confidence_label in {"weak", "limited"}
    warning_text = " ".join(result.warnings).lower()
    assert "project" in warning_text
    assert "work" in warning_text
    assert "highlight" in warning_text or "outcome" in warning_text
    assert result.missing_info_questions


def test_rich_resume_produces_useful_profile() -> None:
    case = _case("rich_resume_full_profile")
    result = evaluate_profile_review_case(
        case_id=case["case_id"],
        title=case["title"],
        resume_text=case["resume_text"],
        target_roles=case["target_roles"],
        expected=ResumeProfileExpectedSignals(**case["expected"]),
        known_limitations=case["known_limitations"],
    )

    assert result.skill_hits
    assert result.project_count > 0
    assert result.education_count > 0 or result.work_experience_count > 0
    assert result.confidence_label != "weak"


def test_evaluation_script_output_generation(tmp_path) -> None:
    run(tmp_path)

    summary_json = tmp_path / "summary.json"
    summary_md = tmp_path / "summary.md"
    assert summary_json.exists()
    assert summary_md.exists()
    assert "Case Table" in summary_md.read_text(encoding="utf-8")


def test_current_limitations_are_visible() -> None:
    result = evaluate_profile_review_suite(PROFILE_EVALUATION_CASES)
    embedded = next(case for case in result.cases if case.case_id == "embedded_stm32_chinese")
    research = next(case for case in result.cases if case.case_id == "ml_research_english")

    assert embedded.failed_checks or research.failed_checks
    assert result.known_limitations
