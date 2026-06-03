from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem
from app.services.errors import JobAgentError


def _load_demo_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_brief_rerank.py"
    spec = importlib.util.spec_from_file_location("demo_brief_rerank", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = _load_demo_module()


def _build_report() -> JobBriefReport:
    jd_text = "Responsibilities: Build AI systems.\nRequirements: Python, PyTorch.\n" + ("detail " * 120)
    job = SearchResultItem(
        title="AI Engineer",
        company="Example AI",
        location="Shenzhen",
        url="https://example.com/jobs/ai-engineer",
        snippet="Build AI systems for healthcare workflows.",
        source="local_db",
        retrieved_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        responsibilities=["Build AI systems."],
        requirements=["Python and PyTorch."],
        skills=["Python", "PyTorch"],
        jd_text=jd_text,
        is_full_jd=True,
        confidence=0.9,
        quality_label="full_jd",
    )
    match_report = MatchReport(
        overall_score=86.0,
        skill_score=88.0,
        project_score=82.0,
        experience_score=80.0,
        keyword_coverage=84.0,
        matched_points=["Strong Python alignment"],
        missing_points=["Need more healthcare examples"],
        risks=["Domain depth is still light"],
        evidence=["Built an AI workflow demo"],
        apply_recommendation="Apply after highlighting PyTorch work.",
        short_term_suggestions=["Move PyTorch evidence higher"],
        long_term_suggestions=["Add more production AI examples"],
    )
    item = JobRecommendationItem(
        rank=1,
        job=job,
        match_report=match_report,
        fit_score=86.0,
        advice="Apply after highlighting PyTorch work.",
        scoring_quality="full_jd",
        fit_reasons=["Strong Python alignment"],
        risk_points=["Domain depth is still light", "Need more healthcare examples"],
    )
    return JobBriefReport(
        query="AI PyTorch Shenzhen",
        provider="local_db",
        total_jobs=1,
        recommended_jobs=[item],
        top_skills=["Python", "PyTorch"],
        market_summary="Found 1 reranked job.",
        application_strategy=["Prioritize the top role first."],
        scoring_quality_summary="Scoring quality mix: full_jd=1, partial_jd=0, external_link_only=0, snippet_only=0.",
    )


def test_run_demo_writes_raw_and_sanitized_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(demo, "rerank_brief_run", lambda *args, **kwargs: _build_report())
    args = demo.build_parser().parse_args(
        [
            "--run-id",
            "abc123run",
            "--limit",
            "3",
            "--output-dir",
            str(tmp_path / "demo_runs"),
            "--publish-docs-dir",
            str(tmp_path / "docs_demo_runs"),
            "--publish-sanitized",
        ]
    )

    result = demo.run_demo(args, timestamp="20260603T040404Z")

    assert result.summary["run_id"] == "abc123run"
    assert (result.output_dir / "brief_summary.json").exists()
    assert (result.output_dir / "recommended_jobs.json").exists()
    assert result.publish_dir is not None
    assert (result.publish_dir / "recommended_jobs_preview.json").exists()

    preview_jobs = json.loads(
        (result.publish_dir / "recommended_jobs_preview.json").read_text(encoding="utf-8")
    )
    assert "jd_text" not in preview_jobs[0]
    assert len(preview_jobs[0]["jd_text_preview"]) <= 500


def test_run_demo_raises_clear_error_when_rerank_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        demo,
        "rerank_brief_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(JobAgentError("Brief run not found", "brief_run_not_found")),
    )
    args = demo.build_parser().parse_args(
        [
            "--run-id",
            "missing-run",
            "--output-dir",
            str(tmp_path / "demo_runs"),
        ]
    )

    with pytest.raises(ValueError, match="Brief run not found"):
        demo.run_demo(args, timestamp="20260603T050505Z")
