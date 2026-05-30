from __future__ import annotations

import pytest

from app.agents.jd_analysis_agent import analyze_jd
from app.agents.match_agent import analyze_match
from app.agents.project_challenge_agent import generate_project_challenges
from app.agents.report_agent import generate_report
from app.agents.resume_optimize_agent import optimize_resume
from app.agents.resume_parse_agent import parse_resume
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ProjectChallengeReport, ResumeOptimizationResult
from app.schemas.resume import ResumeProfile
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


def test_mock_agents_return_shared_schemas() -> None:
    resume_profile = parse_resume(SAMPLE_RESUME)
    job_analysis = analyze_jd(SAMPLE_JD)
    match_report = analyze_match(resume_profile, job_analysis)
    optimization_result = optimize_resume(
        SAMPLE_RESUME,
        resume_profile,
        job_analysis,
        match_report,
    )
    challenge_report = generate_project_challenges(resume_profile, job_analysis)
    markdown_report = generate_report(
        resume_profile=resume_profile,
        job_analysis=job_analysis,
        match_report=match_report,
        optimization_result=optimization_result,
        project_challenge_report=challenge_report,
    )

    assert isinstance(resume_profile, ResumeProfile)
    assert isinstance(job_analysis, JobAnalysis)
    assert isinstance(match_report, MatchReport)
    assert isinstance(optimization_result, ResumeOptimizationResult)
    assert isinstance(challenge_report, ProjectChallengeReport)
    assert "匹配度总览" in markdown_report


def test_resume_parse_agent_rejects_empty_resume() -> None:
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        parse_resume("")
