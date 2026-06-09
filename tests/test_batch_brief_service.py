from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.match import MatchReport
from app.schemas.profile_review import ProfileSearchContext, ResumeProfileUserEdits
from app.schemas.resume import ResumeProfile
from app.schemas.search import SearchResultItem, SearchResultSet
from app.services.batch_brief_service import (
    build_brief_from_jobs,
    build_brief_from_search,
    build_profile_enhanced_query,
    build_profile_search_plan,
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
    quality_label: str | None = None,
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
        quality_label=quality_label,
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


def _build_profile_context(
    *,
    skills: list[str] | None = None,
    target_roles: list[str] | None = None,
    preferred_locations: list[str] | None = None,
    additional_skills: list[str] | None = None,
    constraints: list[str] | None = None,
) -> ProfileSearchContext:
    return ProfileSearchContext(
        confirmed_profile=ResumeProfile(
            raw_text="profile context test resume",
            skills=skills if skills is not None else ["Python", "FastAPI"],
        ),
        user_confirmed_data=ResumeProfileUserEdits(
            target_roles=(
                target_roles
                if target_roles is not None
                else ["AI Agent Engineer"]
            ),
            preferred_locations=(
                preferred_locations
                if preferred_locations is not None
                else ["Shenzhen"]
            ),
            additional_skills=(
                additional_skills
                if additional_skills is not None
                else ["LangGraph"]
            ),
            constraints=constraints if constraints is not None else [],
        ),
    )


def test_profile_search_plan_preserves_query_and_separates_terms() -> None:
    profile_context = _build_profile_context(
        skills=["Python", "FastAPI"],
        target_roles=["AI Agent Engineer"],
        preferred_locations=["Shenzhen"],
        additional_skills=["LangGraph"],
    )

    plan = build_profile_search_plan(" backend   internship ", profile_context)

    assert plan.original_query == "backend internship"
    assert plan.effective_query.startswith("backend internship")
    assert plan.role_terms == ["AI Agent Engineer"]
    assert plan.location_terms == ["Shenzhen"]
    assert "LangGraph" in plan.skill_terms
    assert "Python" in plan.skill_terms
    assert plan.profile_context_used is True


def test_profile_search_plan_prioritizes_additional_skills() -> None:
    profile_context = _build_profile_context(
        skills=["Python", "FastAPI", "SQLite"],
        additional_skills=["LangGraph", "FastAPI"],
    )

    plan = build_profile_search_plan("backend internship", profile_context)

    assert plan.skill_terms == ["LangGraph", "FastAPI", "Python", "SQLite"]


def test_profile_search_plan_can_use_profile_context_without_query() -> None:
    profile_context = _build_profile_context(
        skills=["Python"],
        target_roles=["AI Agent Engineer"],
    )

    plan = build_profile_search_plan("", profile_context)

    assert plan.original_query == ""
    assert "AI Agent Engineer" in plan.effective_query
    assert "effective query was generated only from profile context" in plan.warnings


def test_profile_search_plan_without_context_keeps_old_query() -> None:
    plan = build_profile_search_plan("backend internship", None)

    assert plan.original_query == "backend internship"
    assert plan.effective_query == "backend internship"
    assert plan.profile_context_used is False


def test_profile_search_plan_empty_query_without_context_is_empty() -> None:
    plan = build_profile_search_plan("", None)

    assert plan.effective_query == ""
    assert plan.profile_context_used is False


def test_profile_search_plan_warns_for_missing_profile_context_sections() -> None:
    profile_context = _build_profile_context(
        skills=[],
        target_roles=[],
        preferred_locations=[],
        additional_skills=[],
    )

    plan = build_profile_search_plan("backend internship", profile_context)

    assert "profile_context is empty" in plan.warnings
    assert "profile_context has no target roles" in plan.warnings
    assert "profile_context has no preferred locations" in plan.warnings
    assert "profile_context has no skills" in plan.warnings


def test_profile_search_plan_warns_when_effective_query_is_truncated() -> None:
    profile_context = _build_profile_context(
        constraints=[
            "backend " * 30,
            "ai application " * 30,
            "platform engineering " * 30,
        ],
    )

    plan = build_profile_search_plan("x" * 280, profile_context)

    assert len(plan.effective_query) <= 300
    assert "effective query was truncated to 300 characters" in plan.warnings


def test_profile_enhanced_query_delegates_to_profile_search_plan() -> None:
    profile_context = _build_profile_context()

    effective = build_profile_enhanced_query("backend internship", profile_context)

    assert effective == build_profile_search_plan(
        "backend internship",
        profile_context,
    ).effective_query


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
        _build_job(title="Full JD", snippet="full snippet", jd_text="full text", is_full_jd=True, quality_label="full_jd"),
        _build_job(title="Partial JD", snippet="partial snippet", jd_text="partial text", is_full_jd=False, quality_label="partial_jd"),
        _build_job(title="External Link", snippet="详情见外链", jd_text="详情见 https://mp.weixin.qq.com/s/example", is_full_jd=False, quality_label="external_link_only"),
        _build_job(title="Snippet Only", snippet="snippet only", jd_text=None, is_full_jd=False, quality_label="snippet_only"),
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
        "external_link_only",
        "snippet_only",
    ]


def test_scoring_quality_summary_includes_external_link_only(monkeypatch) -> None:
    jobs = [
        _build_job(title="Full JD", snippet="full snippet", jd_text="full text", is_full_jd=True, quality_label="full_jd"),
        _build_job(title="External Link", snippet="详情见外链", jd_text="详情见 https://mp.weixin.qq.com/s/example", quality_label="external_link_only"),
    ]
    monkeypatch.setattr(
        "app.services.batch_brief_service.run_job_analysis_workflow",
        lambda **kwargs: _fake_workflow_result(70.0, label=kwargs["jd_text"]),
    )

    report = build_brief_from_jobs(
        resume_text="resume text",
        query="query",
        provider="local_db",
        jobs=jobs,
    )

    assert "external_link_only=1" in report.scoring_quality_summary


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
