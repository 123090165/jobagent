from __future__ import annotations

from experiments.resume_extraction_compare import (
    EvidenceValidation,
    RunResult,
    aggregate_report,
    evaluate_coverage,
    normalize_output,
    parse_env_file,
    sanitize_error,
    validate_evidence,
)
from tests.fixtures.resumes.profile_review_quality_cases import (
    PROFILE_REVIEW_QUALITY_CASES,
)


def test_parse_env_file_reads_values_without_requiring_process_env(tmp_path) -> None:
    env_file = tmp_path / ".env.deepseek.local"
    env_file.write_text(
        "\n".join(
            [
                "# local only",
                "DEEPSEEK_API_KEY='secret-value'",
                'DEEPSEEK_MODEL="deepseek-test"',
                "JOBAGENT_LLM_TEMPERATURE=0.2",
            ]
        ),
        encoding="utf-8",
    )

    values = parse_env_file(env_file)

    assert values["DEEPSEEK_API_KEY"] == "secret-value"
    assert values["DEEPSEEK_MODEL"] == "deepseek-test"
    assert values["JOBAGENT_LLM_TEMPERATURE"] == "0.2"


def test_normalize_output_fills_shared_schema_defaults() -> None:
    normalized = normalize_output(
        {
            "resume_profile": {
                "name": "Alex",
                "skills": "Python",
            },
            "evidence": {
                "skills": {"value": "Python", "quote": "Python"},
            },
        }
    )

    assert normalized["resume_profile"]["name"] == "Alex"
    assert normalized["resume_profile"]["skills"] == ["Python"]
    assert normalized["resume_profile"]["projects"] == []
    assert normalized["evidence"]["skills"] == [{"value": "Python", "quote": "Python"}]
    assert normalized["quality_warnings"] == []


def test_validate_evidence_accepts_searchable_quotes() -> None:
    resume_text = "Skills: Python\nProject: JobAgent - built APIs.\nEducation: CUHKSZ"
    output = normalize_output(
        {
            "resume_profile": {
                "skills": ["Python"],
                "projects": [{"name": "JobAgent", "description": "built APIs"}],
                "education": [{"school": "CUHKSZ"}],
            },
            "evidence": {
                "skills": [{"value": "Python", "quote": "Python"}],
                "projects": [{"value": "JobAgent", "quote": "JobAgent - built APIs"}],
                "education": [{"value": "CUHKSZ", "quote": "CUHKSZ"}],
            },
        }
    )

    validation = validate_evidence(output, resume_text)

    assert validation.evidence_valid is True
    assert validation.unsupported_count == 0


def test_validate_evidence_counts_missing_or_unsearchable_quotes() -> None:
    resume_text = "Skills: Python"
    output = normalize_output(
        {
            "resume_profile": {
                "skills": ["Python", "Rust"],
            },
            "evidence": {
                "skills": [
                    {"value": "Python", "quote": "Python"},
                    {"value": "Rust", "quote": "Rust production compiler"},
                ],
            },
        }
    )

    validation = validate_evidence(output, resume_text)

    assert validation.evidence_valid is False
    assert validation.unsupported_count >= 1


def test_evaluate_coverage_uses_regression_expectations() -> None:
    case = next(item for item in PROFILE_REVIEW_QUALITY_CASES if item.case_id == "ai_agent_backend")
    output = normalize_output(
        {
            "resume_profile": {
                "skills": ["Python", "FastAPI", "LangGraph", "SQLite"],
                "projects": [{"name": "JobAgent", "description": "FastAPI evaluation"}],
                "work_experiences": [{"role": "Backend Intern", "company": "Example AI Lab"}],
                "education": [{"school": "Shenzhen University", "major": "Computer Science"}],
            },
            "evidence": {},
        }
    )

    coverage = evaluate_coverage(output, case)

    assert coverage["available"] is True
    assert coverage["skills"]["rate"] == 1.0
    assert coverage["projects"]["rate"] == 1.0
    assert coverage["work_experiences"]["rate"] == 1.0
    assert coverage["education"]["rate"] == 1.0


def test_aggregate_report_summarizes_rates_and_stability() -> None:
    output = normalize_output(
        {
            "resume_profile": {"skills": ["Python"]},
            "evidence": {"skills": [{"value": "Python", "quote": "Python"}]},
        }
    )
    results = [
        RunResult(
            mode="direct_one_shot",
            run_index=1,
            schema_valid=True,
            output=output,
            evidence_validation=EvidenceValidation(True, 0, []),
            coverage={"available": False},
        ),
        RunResult(
            mode="direct_one_shot",
            run_index=2,
            schema_valid=False,
            output=output,
            evidence_validation=EvidenceValidation(False, 2, ["missing"]),
            coverage={"available": False},
            call_errors=["failed"],
        ),
    ]

    summary = aggregate_report(results)

    mode = summary["direct_one_shot"]
    assert mode["runs"] == 2
    assert mode["schema_valid_rate"] == 0.5
    assert mode["evidence_valid_rate"] == 0.5
    assert mode["unsupported_field_count"] == 2
    assert mode["call_error_count"] == 1
    assert mode["stability"] == 1.0


def test_sanitize_error_masks_secret_like_values() -> None:
    sanitized = sanitize_error(
        "bad Bearer sk-secretvalue123456 token: abcdefghijklmnopqrstuvwxyz123456"
    )

    assert "Bearer [masked]" in sanitized
    assert "token=[masked]" in sanitized
    assert "abcdefghijklmnopqrstuvwxyz123456" not in sanitized
