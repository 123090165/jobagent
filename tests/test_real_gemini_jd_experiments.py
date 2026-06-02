from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_real_gemini_jd_experiments.py"
    spec = importlib.util.spec_from_file_location("run_real_gemini_jd_experiments", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


experiments = _load_script_module()


def test_load_queries_prefers_explicit_args() -> None:
    queries = experiments.load_queries(
        [" query one ", "query two"],
        None,
        max_runs=5,
    )

    assert queries == ["query one", "query two"]


def test_load_queries_reads_query_file(tmp_path: Path) -> None:
    query_file = tmp_path / "queries.txt"
    query_file.write_text("first query\n\n second query \n", encoding="utf-8")

    queries = experiments.load_queries(None, query_file, max_runs=5)

    assert queries == ["first query", "second query"]


def test_load_queries_uses_defaults_when_none_provided() -> None:
    queries = experiments.load_queries(None, None, max_runs=3)

    assert queries == experiments.DEFAULT_QUERIES[:3]


def test_load_queries_respects_max_runs() -> None:
    queries = experiments.load_queries(
        ["one", "two", "three"],
        None,
        max_runs=2,
    )

    assert queries == ["one", "two"]


def test_classify_run_result_good() -> None:
    run = {
        "selected_title": "AI Agent Engineer",
        "selected_url": "https://careers.example.com/jobs/123",
        "selected_is_full_jd": True,
        "selected_confidence": 0.82,
        "analysis_succeeded": True,
    }

    assert experiments.classify_run_result(run) == experiments.GOOD_STATUS


def test_classify_run_result_partial() -> None:
    run = {
        "selected_title": "AI Agent Engineer",
        "selected_url": "https://careers.example.com/jobs/123",
        "selected_is_full_jd": False,
        "selected_confidence": 0.48,
        "analysis_succeeded": True,
    }

    assert experiments.classify_run_result(run) == experiments.PARTIAL_STATUS


def test_classify_run_result_failed() -> None:
    run = {
        "selected_title": "AI Agent Engineer",
        "selected_url": "https://careers.example.com/jobs/123",
        "selected_is_full_jd": True,
        "selected_confidence": 0.9,
        "analysis_succeeded": False,
    }

    assert experiments.classify_run_result(run) == experiments.FAILED_STATUS


def test_build_markdown_summary_avoids_resume_and_full_jd() -> None:
    run = {
        "query": "agent jobs",
        "status": experiments.PARTIAL_STATUS,
        "selected_title": "AI Agent Engineer",
        "selected_company": "Example Co",
        "selected_url": "https://careers.example.com/jobs/123",
        "selected_is_full_jd": False,
        "selected_confidence": 0.45,
        "selected_jd_text_preview": "Responsibilities and requirements preview only.",
        "url_import_succeeded": False,
        "used_fallback_jd": True,
        "analysis_succeeded": True,
        "notes": ["Fallback JD draft was used."],
        "resume_text": "should never appear",
        "jd_text": "should never appear either",
    }

    summary = experiments.build_markdown_summary(experiments.build_json_summary([run]))

    assert "should never appear" not in summary
    assert "Responsibilities and requirements preview only." not in summary
    assert "Fallback JD draft was used." in summary


def test_build_json_summary_avoids_resume_and_full_jd() -> None:
    run = {
        "query": "agent jobs",
        "status": experiments.GOOD_STATUS,
        "selected_title": "AI Agent Engineer",
        "selected_company": "Example Co",
        "selected_url": "https://careers.example.com/jobs/123",
        "selected_is_full_jd": True,
        "selected_confidence": 0.82,
        "selected_jd_text_preview": "Preview only",
        "url_import_succeeded": True,
        "used_fallback_jd": False,
        "analysis_succeeded": True,
        "notes": ["Gemini marked the result as a full JD."],
        "resume_text": "should never appear",
        "jd_text": "full jd should never appear",
    }

    summary = experiments.build_json_summary([run])

    assert summary["good_runs"] == 1
    assert "resume_text" not in str(summary)
    assert "full jd should never appear" not in str(summary)


def test_build_demo_command_passes_expected_flags() -> None:
    args = argparse.Namespace(
        resume_file="data/samples/sample_resume.md",
        output_dir="demo_runs",
        publish_docs_dir="docs/demo_runs",
        timeout_seconds=60,
        api_base_url="http://127.0.0.1:8000",
        start_api=True,
        try_import_url=True,
        use_llm=True,
        use_langgraph=False,
    )

    command = experiments.build_demo_command(args, "agent jobs", Path("D:/projects/jobagent"))

    assert "--publish-sanitized" in command
    assert "--start-api" in command
    assert "--try-import-url" in command
    assert "--use-llm" in command
    assert "--use-langgraph" not in command
    assert "demo_gemini_search_flow.py" in command[1]


def test_parse_publish_readme_extracts_boolean_like_fields() -> None:
    text = (
        "# Gemini Search Demo Run\n\n"
        "- URL Import Succeeded: False\n"
        "- Used Fallback JD Draft: True\n"
        "- Gemini Returned Full JD: False\n"
    )

    values = experiments.parse_publish_readme(text)

    assert values["URL Import Succeeded"] == "False"
    assert experiments.parse_markdown_bool(values["Used Fallback JD Draft"]) is True
    assert experiments.parse_markdown_bool(values["Gemini Returned Full JD"]) is False
