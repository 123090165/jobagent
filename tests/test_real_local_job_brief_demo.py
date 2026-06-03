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


def _load_demo_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_real_local_job_brief.py"
    spec = importlib.util.spec_from_file_location("demo_real_local_job_brief", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = _load_demo_module()


def _build_report() -> JobBriefReport:
    jd_text = (
        "Responsibilities:\n"
        "- Build AI tooling for healthcare workflows.\n"
        "Requirements:\n"
        "- Strong Python, PyTorch, and signal processing fundamentals.\n"
        + ("JD detail " * 120)
    )
    job = SearchResultItem(
        title="AI Algorithm Engineer",
        company="Example MedTech",
        location="Shenzhen",
        url="https://career.cuhk.edu.cn/job/view/id/468293",
        snippet="Build AI tooling for healthcare workflows.",
        source="cuhksz_career",
        retrieved_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        responsibilities=["Build AI tooling for healthcare workflows."],
        requirements=["Strong Python, PyTorch, and signal processing fundamentals."],
        skills=["Python", "PyTorch", "Signal Processing"],
        jd_text=jd_text,
        is_full_jd=True,
        confidence=0.86,
    )
    match_report = MatchReport(
        overall_score=84.0,
        skill_score=86.0,
        project_score=82.0,
        experience_score=80.0,
        keyword_coverage=85.0,
        matched_points=["Python matches well"],
        missing_points=["Need stronger biosignal examples"],
        risks=["Limited domain proof"],
        evidence=["Built backend AI workflow demo"],
        apply_recommendation="Apply after highlighting PyTorch and healthcare signal projects.",
        short_term_suggestions=["Highlight PyTorch work earlier"],
        long_term_suggestions=["Add more biosignal project evidence"],
    )
    recommendation = JobRecommendationItem(
        rank=1,
        job=job,
        match_report=match_report,
        fit_score=84.0,
        advice="Apply after highlighting PyTorch and healthcare signal projects.",
        scoring_quality="full_jd",
        fit_reasons=["Python matches well"],
        risk_points=["Limited domain proof", "Need stronger biosignal examples"],
    )
    return JobBriefReport(
        query="AI PyTorch 生理信号 深圳",
        provider="local_db",
        total_jobs=1,
        recommended_jobs=[recommendation],
        top_skills=["Python", "PyTorch", "Signal Processing"],
        market_summary="Found 1 local job.",
        application_strategy=["Prioritize the top role first."],
        scoring_quality_summary="Scoring quality mix: full_jd=1, partial_jd=0, snippet_only=0.",
    )


def test_run_demo_raises_clear_error_when_no_public_jobs(tmp_path: Path, monkeypatch) -> None:
    resume_file = tmp_path / "resume.md"
    resume_file.write_text("# Resume\n\nPython FastAPI", encoding="utf-8")
    monkeypatch.setattr(demo, "list_public_job_posts", lambda **kwargs: [])

    args = demo.build_parser().parse_args(
        [
            "--resume-file",
            str(resume_file),
            "--output-dir",
            str(tmp_path / "runs"),
        ]
    )

    with pytest.raises(ValueError, match="No public jobs found. Run collect_cuhksz_jobs.py first."):
        demo.run_demo(args, timestamp="20260603T010101Z")


def test_run_demo_writes_raw_and_sanitized_outputs(tmp_path: Path, monkeypatch) -> None:
    resume_file = tmp_path / "resume.md"
    resume_file.write_text("# Resume\n\nPython PyTorch signal processing", encoding="utf-8")
    monkeypatch.setattr(demo, "list_public_job_posts", lambda **kwargs: [{"id": 1}])
    monkeypatch.setattr(demo, "build_brief_from_search", lambda **kwargs: _build_report())

    args = demo.build_parser().parse_args(
        [
            "--resume-file",
            str(resume_file),
            "--query",
            "AI PyTorch 生理信号 深圳",
            "--limit",
            "5",
            "--output-dir",
            str(tmp_path / "demo_runs"),
            "--publish-docs-dir",
            str(tmp_path / "docs_demo_runs"),
            "--publish-sanitized",
        ]
    )
    result = demo.run_demo(args, timestamp="20260603T020202Z")

    assert result.output_dir.exists()
    assert (result.output_dir / "brief_summary.json").exists()
    assert (result.output_dir / "recommended_jobs.json").exists()
    assert (result.output_dir / "README.md").exists()

    raw_jobs = json.loads((result.output_dir / "recommended_jobs.json").read_text(encoding="utf-8"))
    assert raw_jobs[0]["jd_text"]
    assert raw_jobs[0]["source_url"] == "https://career.cuhk.edu.cn/job/view/id/468293"

    assert result.publish_dir is not None
    assert (result.publish_dir / "brief_summary.json").exists()
    assert (result.publish_dir / "recommended_jobs_preview.json").exists()
    assert (result.publish_dir / "README.md").exists()


def test_publish_sanitized_does_not_write_full_jd_text(tmp_path: Path, monkeypatch) -> None:
    resume_body = "# Resume\n\nPython PyTorch signal processing"
    resume_file = tmp_path / "resume.md"
    resume_file.write_text(resume_body, encoding="utf-8")
    monkeypatch.setattr(demo, "list_public_job_posts", lambda **kwargs: [{"id": 1}])
    monkeypatch.setattr(demo, "build_brief_from_search", lambda **kwargs: _build_report())

    args = demo.build_parser().parse_args(
        [
            "--resume-file",
            str(resume_file),
            "--output-dir",
            str(tmp_path / "demo_runs"),
            "--publish-docs-dir",
            str(tmp_path / "docs_demo_runs"),
            "--publish-sanitized",
        ]
    )
    result = demo.run_demo(args, timestamp="20260603T030303Z")

    preview_jobs = json.loads(
        (result.publish_dir / "recommended_jobs_preview.json").read_text(encoding="utf-8")
    )
    preview_text = preview_jobs[0]["jd_text_preview"]
    full_jd = _build_report().recommended_jobs[0].job.jd_text

    assert "jd_text" not in preview_jobs[0]
    assert len(preview_text) <= 500
    assert preview_text != full_jd

    summary_text = (result.publish_dir / "brief_summary.json").read_text(encoding="utf-8")
    readme_text = (result.publish_dir / "README.md").read_text(encoding="utf-8")
    assert "resume_text" not in summary_text
    assert resume_body not in summary_text
    assert resume_body not in readme_text


def test_run_demo_can_save_brief_run_and_expose_run_id(tmp_path: Path, monkeypatch) -> None:
    resume_file = tmp_path / "resume.md"
    resume_file.write_text("# Resume\n\nPython PyTorch signal processing", encoding="utf-8")
    monkeypatch.setattr(demo, "list_public_job_posts", lambda **kwargs: [{"id": 1}])
    monkeypatch.setattr(demo, "build_brief_from_search", lambda **kwargs: _build_report())
    monkeypatch.setattr(demo, "save_brief_run", lambda report, resume_text: "run123save")

    args = demo.build_parser().parse_args(
        [
            "--resume-file",
            str(resume_file),
            "--output-dir",
            str(tmp_path / "demo_runs"),
            "--save-run",
        ]
    )
    result = demo.run_demo(args, timestamp="20260603T060606Z")

    summary = json.loads((result.output_dir / "brief_summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == "run123save"
    assert result.summary["run_id"] == "run123save"
