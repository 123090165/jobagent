from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem
from app.services.brief_run_storage_service import (
    get_brief_run,
    sanitize_recommendation_for_storage,
    save_brief_run,
)


def _build_report() -> JobBriefReport:
    long_jd = "Responsibilities: Build AI systems.\nRequirements: Python, PyTorch.\n" + ("detail " * 200)
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
        jd_text=long_jd,
        is_full_jd=True,
        confidence=0.9,
        quality_label="full_jd",
    )
    match_report = MatchReport(
        overall_score=88.0,
        skill_score=90.0,
        project_score=84.0,
        experience_score=82.0,
        keyword_coverage=86.0,
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
        fit_score=88.0,
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
        market_summary="Found 1 job.",
        application_strategy=["Prioritize the top role first."],
        scoring_quality_summary="Scoring quality mix: full_jd=1, partial_jd=0, external_link_only=0, snippet_only=0.",
    )


def test_sanitize_recommendation_for_storage_removes_full_jd_text() -> None:
    item = _build_report().recommended_jobs[0]

    payload = sanitize_recommendation_for_storage(item)

    assert "jd_text" not in payload["job"]
    assert payload["job"]["jd_text_preview"]
    assert len(payload["job"]["jd_text_preview"]) <= 500


def test_save_and_get_brief_run_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    report = _build_report()

    run_id = save_brief_run(report, "resume text with private details", database_path=database_path)
    stored = get_brief_run(run_id, database_path=database_path)

    assert run_id
    assert stored is not None
    assert stored["run_id"] == run_id
    assert stored["brief"]["query"] == "AI PyTorch Shenzhen"
    assert stored["brief"]["recommended_jobs"][0]["job"]["title"] == "AI Engineer"
    assert not stored["brief"]["recommended_jobs"][0]["job"].get("jd_text")
    assert stored["brief"]["recommended_jobs"][0]["job"]["jd_text_preview"]


def test_save_brief_run_stores_resume_hash_only(tmp_path: Path) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    report = _build_report()
    resume_text = "resume text with sensitive contact info"

    run_id = save_brief_run(report, resume_text, database_path=database_path)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    run_row = connection.execute(
        "SELECT run_id, resume_hash FROM brief_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(brief_runs)").fetchall()
    }
    item_row = connection.execute(
        "SELECT recommendation_json FROM brief_run_items WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    connection.close()

    assert run_row is not None
    assert run_row["resume_hash"] != resume_text
    assert len(run_row["resume_hash"]) == 64
    assert "resume_text" not in columns

    recommendation_payload = json.loads(item_row["recommendation_json"])
    assert "jd_text" not in recommendation_payload["job"]
    assert recommendation_payload["job"]["jd_text_preview"]
