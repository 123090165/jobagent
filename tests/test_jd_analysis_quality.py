"""回归验证jd analysis quality的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import pytest

from app.prompts.loader import PromptNotFoundError, PromptPathError, load_prompt
from app.schemas.job import JobAnalysis
from app.services.jd_analysis_quality import (
    FEWER_THAN_BASELINE_WARNING,
    RESPONSIBILITIES_METADATA_WARNING,
    SPARSE_REQUIRED_SKILLS_WARNING,
    VERBOSE_SKILL_WARNING,
    evaluate_jd_analysis_quality,
)


SAMPLE_JD = """
Role: AI Agent Backend Intern
Company: Example AI Lab
Location: Shenzhen / Remote

Responsibilities:
- Build Python backend services for AI agent workflow demos.
- Implement FastAPI endpoints, Pydantic schemas, and SQLite-backed persistence.
- Connect LLM or agent workflow components while keeping deterministic fallbacks.

Requirements:
- Python backend development experience.
- FastAPI or similar web framework experience.
- LLM / agent workflow experience.
- SQL database experience.
- Git, testing, and documentation habits.
""".strip()


def make_analysis(
    *,
    required_skills: list[str] | None = None,
    responsibilities: list[str] | None = None,
    keywords: list[str] | None = None,
    job_title: str | None = "AI Agent Backend Intern",
    company: str | None = "Example AI Lab",
    location: str | None = "Shenzhen / Remote",
) -> JobAnalysis:
    """提供 make_analysis 所需的测试行为。"""
    return JobAnalysis(
        raw_jd=SAMPLE_JD,
        job_title=job_title,
        company=company,
        location=location,
        responsibilities=responsibilities
        if responsibilities is not None
        else ["Build Python backend services"],
        required_skills=required_skills
        if required_skills is not None
        else ["Python", "FastAPI", "LLM", "SQL", "Git"],
        keywords=keywords if keywords is not None else ["Python", "FastAPI", "LLM", "SQL", "Git"],
    )


def test_load_existing_prompt() -> None:
    prompt = load_prompt("jd_analysis/system.md")

    assert "JDAnalysisAgent" in prompt
    assert "jd_analysis_v3" in prompt


def test_load_missing_prompt_raises_clear_error() -> None:
    with pytest.raises(PromptNotFoundError, match="Prompt file not found"):
        load_prompt("jd_analysis/missing.md")


def test_load_prompt_blocks_path_traversal() -> None:
    with pytest.raises(PromptPathError):
        load_prompt("../agents/jd_analysis_agent.py")


def test_good_llm_output_does_not_recommend_fallback() -> None:
    report = evaluate_jd_analysis_quality(
        jd_text=SAMPLE_JD,
        llm_analysis=make_analysis(),
        baseline_analysis=make_analysis(required_skills=["Python", "FastAPI", "LLM", "SQL", "Git"]),
    )

    assert report.quality_label == "high"
    assert report.fallback_recommended is False
    assert report.warnings == []


def test_required_skills_empty_recommends_fallback() -> None:
    report = evaluate_jd_analysis_quality(
        jd_text=SAMPLE_JD,
        llm_analysis=make_analysis(required_skills=[], keywords=["Python"]),
    )

    assert SPARSE_REQUIRED_SKILLS_WARNING in report.warnings
    assert report.fallback_recommended is True
    assert report.quality_label == "low"


def test_required_skills_much_fewer_than_baseline_recommends_fallback() -> None:
    report = evaluate_jd_analysis_quality(
        jd_text=SAMPLE_JD,
        llm_analysis=make_analysis(required_skills=["Python", "FastAPI"]),
        baseline_analysis=make_analysis(required_skills=["Python", "FastAPI", "LLM", "SQL", "Git"]),
    )

    assert FEWER_THAN_BASELINE_WARNING in report.warnings
    assert report.fallback_recommended is True


def test_responsibilities_metadata_pollution_warns() -> None:
    report = evaluate_jd_analysis_quality(
        jd_text=SAMPLE_JD,
        llm_analysis=make_analysis(responsibilities=["Role: AI Agent Backend Intern"]),
    )

    assert RESPONSIBILITIES_METADATA_WARNING in report.warnings
    assert report.fallback_recommended is False


def test_very_long_skill_entry_warns() -> None:
    report = evaluate_jd_analysis_quality(
        jd_text=SAMPLE_JD,
        llm_analysis=make_analysis(
            required_skills=[
                "Python backend development with FastAPI SQLite Docker Git testing documentation and model quality review"
            ]
        ),
    )

    assert VERBOSE_SKILL_WARNING in report.warnings
