from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem
from app.services.brief_rerank_service import rerank_brief_run
from app.services.brief_run_storage_service import save_brief_run
from app.services.errors import JobAgentError


def _build_item(
    *,
    rank: int,
    title: str,
    location: str,
    quality: str,
    fit_score: float,
    is_full_jd: bool,
    snippet: str,
) -> JobRecommendationItem:
    job = SearchResultItem(
        title=title,
        company="Example Co",
        location=location,
        url=f"https://example.com/jobs/{title.lower().replace(' ', '-')}",
        snippet=snippet,
        source="local_db",
        retrieved_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        skills=["Python", "PyTorch"],
        jd_text=f"Full JD for {title}" if is_full_jd else None,
        is_full_jd=is_full_jd,
        confidence=0.9 if is_full_jd else 0.45,
        quality_label=quality,
    )
    match_report = MatchReport(
        overall_score=fit_score,
        skill_score=fit_score,
        project_score=fit_score - 2,
        experience_score=fit_score - 4,
        keyword_coverage=fit_score,
        matched_points=[f"matched-{title}"],
        missing_points=[f"missing-{title}"],
        risks=[f"risk-{title}"],
        evidence=[f"evidence-{title}"],
        apply_recommendation=f"recommend-{title}",
        short_term_suggestions=[f"short-{title}"],
        long_term_suggestions=[f"long-{title}"],
    )
    return JobRecommendationItem(
        rank=rank,
        job=job,
        match_report=match_report,
        fit_score=fit_score,
        advice=f"advice-{title}",
        scoring_quality=quality,
        fit_reasons=[f"fit-{title}"],
        risk_points=[f"risk-{title}"],
    )


def _build_report() -> JobBriefReport:
    items = [
        _build_item(
            rank=1,
            title="Signal Research Engineer",
            location="Shenzhen",
            quality="partial_jd",
            fit_score=84.0,
            is_full_jd=False,
            snippet="Biosignal and PyTorch work in Shenzhen.",
        ),
        _build_item(
            rank=2,
            title="PyTorch Platform Engineer",
            location="Remote",
            quality="full_jd",
            fit_score=81.0,
            is_full_jd=True,
            snippet="Build PyTorch platform systems.",
        ),
        _build_item(
            rank=3,
            title="External Link AI Intern",
            location="Shenzhen",
            quality="external_link_only",
            fit_score=90.0,
            is_full_jd=False,
            snippet="External link role with weak details.",
        ),
    ]
    return JobBriefReport(
        query="AI PyTorch Shenzhen",
        provider="local_db",
        total_jobs=3,
        recommended_jobs=items,
        top_skills=["Python", "PyTorch"],
        market_summary="Found 3 jobs.",
        application_strategy=["Prioritize the best match first."],
        scoring_quality_summary="Scoring quality mix: full_jd=1, partial_jd=1, external_link_only=1, snippet_only=0.",
    )


def test_rerank_brief_run_reorders_saved_items_without_research(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    run_id = save_brief_run(_build_report(), "resume text", database_path=database_path)

    reranked = rerank_brief_run(run_id, location_keywords=["shenzhen"], include_keywords=["biosignal"])

    assert reranked.recommended_jobs[0].job.title == "Signal Research Engineer"
    assert "without re-searching" in reranked.market_summary


def test_rerank_brief_run_filters_full_jd_and_excludes_external(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    run_id = save_brief_run(_build_report(), "resume text", database_path=database_path)

    reranked = rerank_brief_run(
        run_id,
        require_full_jd=True,
        exclude_external_link_only=True,
        min_fit_score=80.0,
        limit=5,
    )

    assert len(reranked.recommended_jobs) == 1
    assert reranked.recommended_jobs[0].job.title == "PyTorch Platform Engineer"
    assert reranked.recommended_jobs[0].scoring_quality == "full_jd"


def test_rerank_brief_run_rejects_missing_run() -> None:
    with pytest.raises(JobAgentError) as exc_info:
        rerank_brief_run("missing-run-id")

    assert exc_info.value.error_code == "brief_run_not_found"
    assert exc_info.value.status_code == 404


def test_rerank_brief_run_rejects_empty_results(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    run_id = save_brief_run(_build_report(), "resume text", database_path=database_path)

    with pytest.raises(JobAgentError) as exc_info:
        rerank_brief_run(run_id, exclude_keywords=["engineer", "intern", "platform", "signal"])

    assert exc_info.value.error_code == "brief_rerank_no_results"
