from __future__ import annotations

import json
import os

import pytest

from scripts.run_profile_review_quality_evaluation import load_env_file, main, run
from app.services.profile_review_quality_evaluation import (
    compare_profile_review_quality_suites,
    run_profile_review_quality_suite,
)
from tests.fixtures.resumes.profile_review_quality_cases import (
    PROFILE_REVIEW_QUALITY_CASES,
)


def test_fixtures_contain_at_least_six_cases() -> None:
    assert len(PROFILE_REVIEW_QUALITY_CASES) >= 6


def test_deterministic_suite_runs_without_llm() -> None:
    result = run_profile_review_quality_suite(use_llm_enrichment=False)

    assert result.total_cases >= 6
    assert all(not case.enrichment_enabled for case in result.cases)


def test_llm_suite_runs_with_fake_llm() -> None:
    result = run_profile_review_quality_suite(use_llm_enrichment=True)

    assert result.total_cases >= 6
    assert all(case.enrichment_enabled for case in result.cases)


def test_weak_resume_is_not_marked_strong() -> None:
    result = run_profile_review_quality_suite(use_llm_enrichment=False)
    weak_case = next(case for case in result.cases if case.case_id == "weak_resume")

    assert weak_case.quality_verdict != "strong"
    assert weak_case.baseline_confidence_label in {"weak", "limited"}


def test_every_case_produces_save_payload_ready() -> None:
    result = run_profile_review_quality_suite(use_llm_enrichment=True)

    assert all(case.save_payload_ready for case in result.cases)


def test_comparison_summary_is_generated() -> None:
    deterministic = run_profile_review_quality_suite(use_llm_enrichment=False)
    llm = run_profile_review_quality_suite(use_llm_enrichment=True)
    comparison = compare_profile_review_quality_suites(deterministic, llm)

    assert len(comparison) == deterministic.total_cases


def test_script_writes_json_and_markdown_artifacts(tmp_path) -> None:
    outputs = run(output_dir=tmp_path, mode="both", llm_provider="mock")

    assert outputs.deterministic is not None
    assert outputs.llm_enriched is not None
    assert (tmp_path / "deterministic_summary.json").exists()
    assert (tmp_path / "deterministic_summary.md").exists()
    assert (tmp_path / "llm_enriched_summary.json").exists()
    assert (tmp_path / "llm_enriched_summary.md").exists()
    assert (tmp_path / "comparison_summary.json").exists()
    assert (tmp_path / "comparison_summary.md").exists()
    assert (tmp_path / "cases" / "ai_agent_backend.json").exists()
    assert "Case Table" in (tmp_path / "deterministic_summary.md").read_text(
        encoding="utf-8"
    )


def test_deterministic_quality_suite_has_no_failed_cases() -> None:
    result = run_profile_review_quality_suite(use_llm_enrichment=False)
    cases = {case.case_id: case for case in result.cases}

    assert result.failed_cases == 0
    assert cases["anker_ai_health_algorithm"].quality_verdict in {"strong", "acceptable"}
    assert cases["realistic_business_resume_unstructured"].quality_verdict in {
        "strong",
        "acceptable",
    }
    assert cases["ml_audio_asr"].quality_verdict in {"strong", "acceptable"}
    assert cases["finance_fa_analysis"].quality_verdict in {"strong", "acceptable"}
    assert cases["weak_resume"].quality_verdict != "strong"
    assert cases["ai_agent_backend"].quality_verdict == "strong"
    assert cases["realistic_noisy_chinese_resume"].quality_verdict in {
        "strong",
        "acceptable",
    }


def test_env_file_loads_plain_environment_variables(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env.deepseek.local"
    env_file.write_text(
        "DEEPSEEK_API_KEY=test-secret\nDEEPSEEK_MODEL=deepseek-v4-flash\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    loaded_keys = load_env_file(env_file)

    assert loaded_keys == ["DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"]
    assert "test-secret" == os.environ["DEEPSEEK_API_KEY"]
    assert "deepseek-v4-flash" == os.environ["DEEPSEEK_MODEL"]


def test_missing_env_file_raises_clear_error(tmp_path) -> None:
    missing = tmp_path / ".env.missing.local"

    with pytest.raises(FileNotFoundError) as exc_info:
        load_env_file(missing)
    assert str(missing) in str(exc_info.value)


def test_env_file_secret_does_not_appear_in_logs(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    env_file = tmp_path / ".env.deepseek.local"
    env_file.write_text(
        "DEEPSEEK_API_KEY=super-secret-value\nDEEPSEEK_MODEL=deepseek-v4-flash\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profile_review_quality_evaluation.py",
            "--mode",
            "deterministic",
            "--llm-provider",
            "deepseek",
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
        ],
    )

    main()

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["env_file_loaded"] is True
    assert "super-secret-value" not in captured.out
    assert "super-secret-value" not in captured.err
