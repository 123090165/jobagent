from __future__ import annotations

from app.agents.missing_info_agent import generate_missing_info_report
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport
from app.schemas.resume import ProjectExperience, ResumeProfile


def _build_resume_profile(
    *,
    skills: list[str],
    projects: list[ProjectExperience],
    raw_text: str = "Candidate resume",
) -> ResumeProfile:
    return ResumeProfile(
        raw_text=raw_text,
        skills=skills,
        projects=projects,
    )


def _build_job_analysis(*, required_skills: list[str]) -> JobAnalysis:
    return JobAnalysis(
        raw_jd="JD text",
        required_skills=required_skills,
        keywords=required_skills,
    )


def _build_match_report(overall_score: float = 52.0) -> MatchReport:
    return MatchReport(
        overall_score=overall_score,
        skill_score=50.0,
        project_score=55.0,
        experience_score=48.0,
        keyword_coverage=40.0,
        apply_recommendation="补强后再投递",
    )


def test_missing_info_agent_generates_questions_for_missing_skills() -> None:
    resume = _build_resume_profile(
        skills=["Python"],
        projects=[
            ProjectExperience(
                name="项目 1",
                description="Build backend module",
                raw_text="Build backend module",
                technologies=["Python"],
            )
        ],
    )
    job = _build_job_analysis(required_skills=["Python", "FastAPI"])
    report = generate_missing_info_report(resume, job, _build_match_report())

    assert report.questions
    assert any(question.related_skill == "FastAPI" for question in report.questions)
    assert "clarification questions" in report.summary


def test_missing_skill_questions_are_high_priority() -> None:
    resume = _build_resume_profile(
        skills=["Python"],
        projects=[],
    )
    job = _build_job_analysis(required_skills=["FastAPI"])
    report = generate_missing_info_report(resume, job, _build_match_report())

    high_priority_questions = [
        question for question in report.questions if question.related_skill == "FastAPI"
    ]
    assert high_priority_questions
    assert high_priority_questions[0].priority == "high"


def test_missing_info_agent_detects_short_project_description() -> None:
    resume = _build_resume_profile(
        skills=["Python", "FastAPI"],
        projects=[
            ProjectExperience(
                name="短项目",
                description="API demo",
                raw_text="API demo",
                technologies=["Python", "FastAPI"],
            )
        ],
    )
    job = _build_job_analysis(required_skills=["Python", "FastAPI"])
    report = generate_missing_info_report(resume, job, _build_match_report())

    assert any("描述偏短" in question.question for question in report.questions)


def test_missing_info_agent_detects_missing_quant_and_engineering_evidence() -> None:
    resume = _build_resume_profile(
        skills=["Python"],
        projects=[
            ProjectExperience(
                name="项目 1",
                description="Implemented internal tool for team usage",
                raw_text="Implemented internal tool for team usage",
                technologies=["Python"],
            )
        ],
        raw_text="Python internal tool project",
    )
    job = _build_job_analysis(required_skills=["Python"])
    report = generate_missing_info_report(resume, job, _build_match_report())

    assert any("量化结果" in question.question for question in report.questions)
    assert any("测试" in question.question for question in report.questions)
    assert any("数据库" in question.question for question in report.questions)
    assert any("API" in question.question for question in report.questions)
