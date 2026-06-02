from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem, SearchResultSet
from app.services.batch_brief_service import (
    build_brief_from_jobs,
    build_brief_from_search,
)
from app.services.errors import JobAgentError


def _build_job(
    *,
    title: str,
    snippet: str,
    score: float = 70.0,
    skills: list[str] | None = None,
    jd_text: str | None = None,
    is_full_jd: bool = False,
) -> SearchResultItem:
    return SearchResultItem(
        title=title,
        company="Example Co",
        location="Remote",
        url=f"https://example.com/jobs/{title.lower().replace(' ', '-')}",
        snippet=snippet,
        source="mock",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        skills=skills or [],
        jd_text=jd_text,
        is_full_jd=is_full_jd,
        confidence=0.8 if is_full_jd else 0.4,
    )


def _build_match_report(score: float, *, label: str) -> MatchReport:
    return MatchReport(
        overall_score=score,
        skill_score=score,
        project_score=score - 5,
        experience_score=score - 10,
        keyword_coverage=score,
        matched_points=[f"matched-{label}"],
        missing_points=[f"missing-{label}"],
        risks=[f"risk-{label}"],
        evidence=[f"evidence-{label}"],
        apply_recommendation=f"recommend-{label}",
        short_term_suggestions=[f"short-{label}"],
        long_term_suggestions=[f"long-{label}"],
    )


def _fake_workflow_result(score: float, *, label: str):
    return SimpleNamespace(
        final_report=SimpleNamespace(
            match_report=_build_match_report(score, label=label),
        )
    )


def test_build_brief_from_search_returns_job_brief_report(monkeypatch) -> None:
    jobs = [
        _build_job(title="Role A", snippet="Role A snippet", skills=["Python", "FastAPI"], is_full_jd=True),
        _build_job(title="Role B", snippet="Role B snippet", skills=["Python", "SQL"], is_full_jd=True),
    ]

    monkeypatch.setattr(
        "app.services.batch_brief_service.search_jobs",
        lambda query, provider, limit: SearchResultSet(query=query, provider=provider, items=jobs[:limit]),
    )
    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(78.0, label=kwargs["jd_text"]),
    )

    report = build_brief_from_search("resume text", "python backend", provider="mock", limit=2)

    assert report.query == "python backend"
    assert report.provider == "mock"
    assert report.total_jobs == 2
    assert len(report.recommended_jobs) == 2


def test_recommended_jobs_count_matches_limit(monkeypatch) -> None:
    jobs = [
        _build_job(title=f"Role {index}", snippet=f"snippet-{index}", is_full_jd=True)
        for index in range(1, 6)
    ]

    monkeypatch.setattr(
        "app.services.batch_brief_service.search_jobs",
        lambda query, provider, limit: SearchResultSet(query=query, provider=provider, items=jobs[:limit]),
    )
    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(65.0, label="same"),
    )

    report = build_brief_from_search("resume text", "query", limit=3)

    assert len(report.recommended_jobs) == 3


def test_recommendations_are_sorted_by_fit_score_desc(monkeypatch) -> None:
    jobs = [
        _build_job(title="Role A", snippet="job-a", is_full_jd=True),
        _build_job(title="Role B", snippet="job-b", is_full_jd=True),
        _build_job(title="Role C", snippet="job-c", is_full_jd=True),
    ]
    score_map = {"job-a": 61.0, "job-b": 88.0, "job-c": 73.0}

    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(score_map[kwargs["jd_text"]], label=kwargs["jd_text"]),
    )

    report = build_brief_from_jobs(
        resume_text="resume text",
        query="query",
        provider="mock",
        jobs=jobs,
    )

    assert [item.job.title for item in report.recommended_jobs] == ["Role B", "Role C", "Role A"]
    assert [item.rank for item in report.recommended_jobs] == [1, 2, 3]


def test_recommendation_items_include_required_fields(monkeypatch) -> None:
    job = _build_job(title="Role A", snippet="job-a", is_full_jd=True)
    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(82.0, label="job-a"),
    )

    report = build_brief_from_jobs(
        resume_text="resume text",
        query="query",
        provider="mock",
        jobs=[job],
    )

    item = report.recommended_jobs[0]
    assert item.rank == 1
    assert item.job.title == "Role A"
    assert item.match_report.overall_score == 82.0
    assert item.fit_score == 82.0
    assert item.advice == "recommend-job-a"
    assert item.scoring_quality == "full_jd"
    assert item.fit_reasons == ["matched-job-a"]
    assert item.risk_points == ["risk-job-a", "missing-job-a"]


def test_scoring_quality_values_are_detected(monkeypatch) -> None:
    jobs = [
        _build_job(title="Full JD", snippet="full snippet", jd_text="full text", is_full_jd=True),
        _build_job(title="Partial JD", snippet="partial snippet", jd_text="partial text", is_full_jd=False),
        _build_job(title="Snippet Only", snippet="snippet only", jd_text=None, is_full_jd=False),
    ]
    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(70.0, label=kwargs["jd_text"]),
    )

    report = build_brief_from_jobs(
        resume_text="resume text",
        query="query",
        provider="mock",
        jobs=jobs,
    )

    assert [item.scoring_quality for item in report.recommended_jobs] == [
        "full_jd",
        "partial_jd",
        "snippet_only",
    ]


def test_top_skills_are_collected_and_deduped(monkeypatch) -> None:
    jobs = [
        _build_job(title="Role A", snippet="job-a", skills=["Python", "FastAPI", "SQL"]),
        _build_job(title="Role B", snippet="job-b", skills=["Python", "LLM", "FastAPI"]),
    ]
    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(60.0, label="shared"),
    )

    report = build_brief_from_jobs(
        resume_text="resume text",
        query="query",
        provider="mock",
        jobs=jobs,
    )

    assert report.top_skills == ["Python", "FastAPI", "SQL", "LLM"]


def test_build_brief_from_search_rejects_empty_resume() -> None:
    with pytest.raises(JobAgentError) as exc_info:
        build_brief_from_search("", "query")

    assert exc_info.value.error_code == "brief_resume_empty"


def test_build_brief_from_search_rejects_empty_query() -> None:
    with pytest.raises(JobAgentError) as exc_info:
        build_brief_from_search("resume text", "   ")

    assert exc_info.value.error_code == "brief_query_empty"


@pytest.mark.parametrize("invalid_limit", [0, 11])
def test_build_brief_from_search_rejects_invalid_limit(invalid_limit: int) -> None:
    with pytest.raises(JobAgentError) as exc_info:
        build_brief_from_search("resume text", "query", limit=invalid_limit)

    assert exc_info.value.error_code == "brief_limit_invalid"


def test_build_brief_from_jobs_rejects_empty_jobs() -> None:
    with pytest.raises(JobAgentError) as exc_info:
        build_brief_from_jobs(
            resume_text="resume text",
            query="query",
            provider="mock",
            jobs=[],
        )

    assert exc_info.value.error_code == "brief_jobs_empty"


def test_build_brief_from_jobs_rejects_empty_job_text(monkeypatch) -> None:
    job = _build_job(title="Role A", snippet="   ", jd_text=None, is_full_jd=False)

    with pytest.raises(JobAgentError) as exc_info:
        build_brief_from_jobs(
            resume_text="resume text",
            query="query",
            provider="mock",
            jobs=[job],
        )

    assert exc_info.value.error_code == "brief_job_text_empty"
