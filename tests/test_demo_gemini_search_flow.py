from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_demo_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_gemini_search_flow.py"
    spec = importlib.util.spec_from_file_location("demo_gemini_search_flow", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo = _load_demo_module()


def test_build_fallback_jd_text_includes_core_fields() -> None:
    item = {
        "title": "AI Agent Developer",
        "company": "Example Co",
        "location": "Shenzhen",
        "snippet": "Build agent workflows with Python.",
        "url": "https://example.com/jobs/1",
    }

    text = demo.build_fallback_jd_text(item)

    assert "AI Agent Developer" in text
    assert "Example Co" in text
    assert "Shenzhen" in text
    assert "Build agent workflows with Python." in text
    assert "https://example.com/jobs/1" in text


def test_select_first_search_item_rejects_empty_items() -> None:
    with pytest.raises(ValueError, match="Search returned no items"):
        demo.select_first_search_item({"items": []})


def test_validate_resume_file_rejects_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.md"
    with pytest.raises(ValueError, match="does not exist"):
        demo.validate_resume_file(missing_file)


def test_validate_resume_file_rejects_unsupported_suffix(tmp_path: Path) -> None:
    pdf_file = tmp_path / "resume.pdf"
    pdf_file.write_text("resume", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.txt or \.md"):
        demo.validate_resume_file(pdf_file)


def test_build_analysis_payload_defaults_to_save_result_false() -> None:
    payload = demo.build_analysis_payload("resume", "jd")

    assert payload["save_result"] is False
    assert payload["use_llm_jd"] is False
    assert payload["use_langgraph_workflow"] is False


def test_build_analysis_payload_carries_llm_and_langgraph_flags() -> None:
    payload = demo.build_analysis_payload(
        "resume",
        "jd",
        use_llm=True,
        use_langgraph=True,
        save_result=True,
    )

    assert payload["use_llm_jd"] is True
    assert payload["use_llm_resume_optimize"] is True
    assert payload["use_llm_project_challenge"] is True
    assert payload["use_langgraph_workflow"] is True
    assert payload["save_result"] is True


def test_create_demo_output_dir_stays_under_base_dir(tmp_path: Path) -> None:
    output_dir = demo.create_demo_output_dir(tmp_path, "20260601T010101Z")

    assert output_dir.parent == tmp_path
    assert output_dir.name == "20260601T010101Z"
    assert output_dir.exists()


def test_create_publish_output_dir_stays_under_docs_demo_runs(tmp_path: Path) -> None:
    base_dir = tmp_path / "docs" / "demo_runs"
    output_dir = demo.create_publish_output_dir(base_dir, "20260601T010101Z")

    assert output_dir.parent == base_dir
    assert output_dir.name == "20260601T010101Z"
    assert output_dir.exists()


def test_build_sanitized_search_summary_does_not_include_resume_text() -> None:
    payload = {
        "provider": "gemini_cli",
        "items": [
            {
                "title": "AI Agent Developer",
                "company": "Example Co",
                "location": "Remote",
                "url": "https://example.com/jobs/1",
                "snippet": "Build agent workflows." * 40,
                "source": "gemini_cli",
                "resume_text": "should never be copied",
            }
        ],
    }

    summary = demo.build_sanitized_search_summary("ai agent", payload, payload["items"][0])

    assert "resume_text" not in summary
    assert len(summary["selected_snippet_preview"]) <= 300


def test_build_sanitized_analysis_summary_does_not_include_resume_text() -> None:
    analysis_response = {
        "record_id": None,
        "resume_profile": {
            "raw_text": "secret resume body",
            "skills": ["Python", "FastAPI"],
        },
        "job_analysis": {
            "required_skills": ["Python", "FastAPI", "Docker"],
        },
        "match_report": {"overall_score": 88},
        "workflow_steps": [
            {"name": "ResumeParseAgent", "mode": "mock"},
            {"name": "JDAnalysisAgent", "mode": "fallback"},
        ],
    }

    summary = demo.build_sanitized_analysis_summary(analysis_response, warnings=["warning"])

    assert summary["success"] is True
    assert summary["matched_skills"] == ["Python", "FastAPI"]
    assert summary["missing_skills"] == ["Docker"]
    assert "resume_text" not in summary
    assert "raw_text" not in summary


def test_build_report_excerpt_is_capped_at_1200_chars() -> None:
    analysis_response = {
        "job_analysis": {"job_title": "AI Agent Developer"},
        "match_report": {
            "overall_score": 75,
            "missing_points": [f"missing-{index}" for index in range(20)],
        },
        "optimization_result": {
            "overall_issues": [f"issue-{index}" for index in range(20)],
        },
        "project_challenge_report": {
            "interviewer_concerns": [f"concern-{index}" for index in range(20)],
        },
    }

    excerpt = demo.build_report_excerpt(analysis_response)

    assert len(excerpt) <= 1200
    assert "AI Agent Developer" in excerpt


def test_build_run_metadata_contains_expected_safety_flags() -> None:
    metadata = demo.build_run_metadata(
        timestamp="20260601T010101Z",
        api_base_url="http://127.0.0.1:8000",
        query="agent jobs",
        start_api=True,
        try_import_url=True,
        use_llm=False,
        use_langgraph=False,
        save_result=False,
        gemini_cli_command_overridden=True,
    )

    assert metadata["flags"]["gemini_cli_command_overridden"] is True
    assert metadata["safety"]["resume_text_uploaded_to_gemini_cli"] is False
    assert metadata["safety"]["database_write_default"] is False
    assert metadata["safety"]["deletes_files"] is False
    assert metadata["safety"]["shell_true"] is False
