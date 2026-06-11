from __future__ import annotations

import pytest

from app.agents.match_agent import run_match_agent
from app.agents.project_challenge_agent import run_project_challenge_agent
from app.agents.report_agent import generate_report
from app.agents.resume_optimize_agent import run_resume_optimize_agent
from app.schemas.job import JobAnalysis
from app.schemas.resume import ProjectExperience, ResumeProfile
from app.services.llm_service import LLMServiceError
from app.services.mock_pipeline import run_mock_pipeline
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


class FailingLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        raise LLMServiceError("fake workflow failure")


class ResumeOptimizeLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "overall_issues": ["Need clearer API alignment to the JD."],
            "keywords_to_add": ["REST API"],
            "skills_section_suggestions": ["Move FastAPI and REST API higher in the skills section."],
            "project_rewrite_suggestions": [
                {
                    "original": "JobAgent analysis tool",
                    "suggestion": "Emphasize API, schema, and testing responsibilities in the existing JobAgent project.",
                    "reason": "Rewrite existing evidence only.",
                }
            ],
            "jd_targeted_bullets": ["Highlight API design and test coverage from the existing project."],
            "do_not_exaggerate": ["Do not add tools you have not actually used."],
            "missing_info_needed": ["Add real metrics if you have them."],
        }


class ProjectChallengeLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "question": "How did you use the provided evidence to satisfy this requirement?",
            "why_asked": "It validates whether the candidate can explain real project evidence.",
            "expected_answer_points": ["implementation detail", "personal ownership"],
            "risk_level": "medium",
            "question_type": "technical",
        }


def test_job_analysis_workflow_records_step_trace() -> None:
    result = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert result.final_report.markdown_report
    assert result.final_report.analysis_quality
    assert result.final_report.analysis_quality.overall_quality_label in {"strong", "medium", "limited", "weak"}
    assert "Analysis Quality" in result.final_report.markdown_report
    assert "JD-Resume Evidence Chain" in result.final_report.markdown_report
    assert "### Requirement:" in result.final_report.markdown_report
    assert result.state.resume_profile is not None
    assert result.state.job_analysis is not None
    assert result.state.match_report is not None
    assert [step.name for step in result.state.steps] == [
        "ResumeParseAgent",
        "JDAnalysisAgent",
        "MatchAgent",
        "ResumeOptimizeAgent",
        "ProjectInterviewAgent",
        "ReportAgent",
    ]
    assert all(step.status == "completed" for step in result.state.steps)
    assert {step.mode for step in result.state.steps} == {"mock"}
    assert all(step.guardrails for step in result.state.steps)
    assert result.state.workflow_run_id
    assert all(step.workflow_run_id == result.state.workflow_run_id for step in result.state.steps)
    assert all(step.duration_ms >= 0 for step in result.state.steps)
    assert result.final_report.match_report.requirement_matches
    assert result.final_report.optimization_result.rewrite_suggestions
    assert result.final_report.project_challenge_report.grounded_questions


def test_match_agent_builds_requirement_matches_with_evidence() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI SQLite backend project",
        skills=["Python", "FastAPI"],
        projects=[
            ProjectExperience(
                name="Tracker API",
                description="Built backend APIs with FastAPI and SQLite.",
                technologies=["FastAPI", "SQLite"],
                highlights=["Designed REST endpoints for application tracking."],
                raw_text="Built backend APIs with FastAPI and SQLite.",
            )
        ],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need FastAPI and SQL experience.",
        required_skills=["FastAPI", "SQL"],
        responsibilities=["Build backend APIs"],
        keywords=["FastAPI", "SQL"],
    )

    report = run_match_agent(resume_profile, job_analysis).output

    fastapi_match = next(item for item in report.requirement_matches if "FastAPI" in item.requirement)
    assert fastapi_match.match_level == "matched"
    assert fastapi_match.resume_evidence


def test_match_agent_marks_missing_requirement_with_gap_and_hint() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI backend project",
        skills=["Python", "FastAPI"],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need Kubernetes experience.",
        required_skills=["Kubernetes"],
        keywords=["Kubernetes"],
    )

    report = run_match_agent(resume_profile, job_analysis).output

    kubernetes_match = next(item for item in report.requirement_matches if "Kubernetes" in item.requirement)
    assert kubernetes_match.match_level == "missing"
    assert kubernetes_match.gap_reason
    assert kubernetes_match.improvement_hint


def test_resume_optimize_agent_builds_evidence_based_rewrite_suggestions() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI SQLite backend project",
        skills=["Python", "FastAPI"],
        projects=[
            ProjectExperience(
                name="Tracker API",
                description="Built backend APIs with FastAPI and SQLite.",
                technologies=["FastAPI", "SQLite"],
                highlights=["Designed REST endpoints for application tracking."],
                raw_text="Built backend APIs with FastAPI and SQLite.",
            )
        ],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need FastAPI and SQL experience.",
        required_skills=["FastAPI", "SQL"],
        keywords=["FastAPI", "SQL"],
    )
    match_report = run_match_agent(resume_profile, job_analysis).output

    result = run_resume_optimize_agent(
        resume_profile.raw_text,
        resume_profile,
        job_analysis,
        match_report,
    ).output

    assert result.rewrite_suggestions
    fastapi_item = next(item for item in result.rewrite_suggestions if "FastAPI" in item.linked_requirement)
    assert "FastAPI" in fastapi_item.suggested_bullet
    assert fastapi_item.evidence_source


def test_resume_optimize_agent_keeps_missing_requirement_as_gap() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI backend project",
        skills=["Python", "FastAPI"],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need Kubernetes experience.",
        required_skills=["Kubernetes"],
        keywords=["Kubernetes"],
    )
    match_report = run_match_agent(resume_profile, job_analysis).output

    result = run_resume_optimize_agent(
        resume_profile.raw_text,
        resume_profile,
        job_analysis,
        match_report,
    ).output

    k8s_item = next(item for item in result.rewrite_suggestions if "Kubernetes" in item.linked_requirement)
    assert k8s_item.match_level == "missing"
    assert "If" in k8s_item.suggested_bullet
    assert not k8s_item.evidence_source


def test_project_challenge_agent_builds_grounded_questions_from_match_evidence() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI SQLite backend project",
        skills=["Python", "FastAPI"],
        projects=[
            ProjectExperience(
                name="Tracker API",
                description="Built backend APIs with FastAPI and SQLite.",
                technologies=["FastAPI", "SQLite"],
                highlights=["Designed REST endpoints for application tracking."],
                raw_text="Built backend APIs with FastAPI and SQLite.",
            )
        ],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need FastAPI and SQL experience.",
        required_skills=["FastAPI", "SQL"],
        keywords=["FastAPI", "SQL"],
    )
    match_report = run_match_agent(resume_profile, job_analysis).output

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        match_report=match_report,
    ).output

    assert result.grounded_questions
    item = next(question for question in result.grounded_questions if "FastAPI" in question.linked_requirement)
    assert item.related_resume_evidence
    assert item.expected_answer_points


def test_project_challenge_agent_keeps_missing_requirement_as_honest_gap() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI backend project",
        skills=["Python", "FastAPI"],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need Kubernetes experience.",
        required_skills=["Kubernetes"],
        keywords=["Kubernetes"],
    )
    match_report = run_match_agent(resume_profile, job_analysis).output

    result = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        match_report=match_report,
    ).output

    k8s_item = next(item for item in result.grounded_questions if "Kubernetes" in item.linked_requirement)
    assert k8s_item.match_level == "missing"
    assert not k8s_item.related_resume_evidence
    assert (
        "honest" in k8s_item.question.lower()
        or "experience boundary" in k8s_item.question.lower()
    )
    assert k8s_item.expected_answer_points


def test_generate_report_renders_evidence_chain_with_linked_rewrite_and_challenge() -> None:
    resume_profile = ResumeProfile(
        raw_text="Python FastAPI SQLite backend project",
        skills=["Python", "FastAPI"],
        projects=[
            ProjectExperience(
                name="Tracker API",
                description="Built backend APIs with FastAPI and SQLite.",
                technologies=["FastAPI", "SQLite"],
                highlights=["Designed REST endpoints for application tracking."],
                raw_text="Built backend APIs with FastAPI and SQLite.",
            )
        ],
    )
    job_analysis = JobAnalysis(
        raw_jd="Need FastAPI and Kubernetes experience.",
        required_skills=["FastAPI", "Kubernetes"],
        responsibilities=["Build backend APIs"],
        keywords=["FastAPI", "Kubernetes"],
    )
    match_report = run_match_agent(resume_profile, job_analysis).output
    optimization_result = run_resume_optimize_agent(
        resume_profile.raw_text,
        resume_profile,
        job_analysis,
        match_report,
    ).output
    project_challenge_report = run_project_challenge_agent(
        resume_profile,
        job_analysis,
        match_report=match_report,
    ).output

    markdown_report = generate_report(
        resume_profile=resume_profile,
        job_analysis=job_analysis,
        match_report=match_report,
        optimization_result=optimization_result,
        project_challenge_report=project_challenge_report,
    )

    assert "JD-Resume Evidence Chain" in markdown_report
    assert "### Requirement: FastAPI" in markdown_report
    assert "### Requirement: Kubernetes" in markdown_report
    assert "- Match level: matched" in markdown_report
    assert "- Match level: missing" in markdown_report
    assert "- Rewrite suggestion:" in markdown_report
    assert "- Interview challenge:" in markdown_report
    assert "Not found" in markdown_report


def test_analysis_quality_warns_when_resume_lacks_project_and_work_evidence() -> None:
    sparse_resume = "Skills: Python, FastAPI"
    result = run_job_analysis_workflow(sparse_resume, SAMPLE_JD).final_report

    assert "resume has no project evidence" in result.analysis_quality.warnings
    assert "resume has no work experience evidence" in result.analysis_quality.warnings
    assert result.analysis_quality.resume_quality_label in {"limited", "weak"}


def test_analysis_quality_warns_when_jd_is_too_short() -> None:
    short_jd = "Backend Engineer"
    result = run_job_analysis_workflow(SAMPLE_RESUME, short_jd).final_report

    assert result.analysis_quality.jd_quality_label in {"limited", "weak"}
    assert any("JD" in warning or "jd" in warning for warning in result.analysis_quality.warnings)


def test_mock_pipeline_delegates_to_workflow_without_changing_contract() -> None:
    pipeline_report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)
    workflow_report = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD).final_report

    assert pipeline_report.model_dump() == workflow_report.model_dump()


def test_job_analysis_workflow_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        run_job_analysis_workflow("", SAMPLE_JD)

    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        run_job_analysis_workflow(SAMPLE_RESUME, "")


def test_job_analysis_workflow_records_llm_fallback_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_jd=True,
        jd_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    jd_step = next(step for step in result.state.steps if step.name == "JDAnalysisAgent")
    assert jd_step.mode == "fallback"
    assert jd_step.fallback_reason == "LLMServiceError"
    assert "mock" in jd_step.summary
    assert result.final_report.job_analysis.required_skills


def test_job_analysis_workflow_records_resume_optimize_llm_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_resume_optimize=True,
        resume_optimize_llm_service=ResumeOptimizeLLMService(),  # type: ignore[arg-type]
    )

    optimize_step = next(step for step in result.state.steps if step.name == "ResumeOptimizeAgent")
    assert optimize_step.mode == "llm"
    assert optimize_step.fallback_reason is None
    assert "LLM" in optimize_step.summary
    assert result.final_report.optimization_result.keywords_to_add == ["REST API"]


def test_job_analysis_workflow_records_resume_optimize_fallback_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_resume_optimize=True,
        resume_optimize_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    optimize_step = next(step for step in result.state.steps if step.name == "ResumeOptimizeAgent")
    assert optimize_step.mode == "fallback"
    assert optimize_step.fallback_reason == "LLMServiceError"
    assert "mock" in optimize_step.summary
    assert result.final_report.optimization_result.jd_targeted_bullets


def test_job_analysis_workflow_records_project_challenge_llm_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_project_challenge=True,
        project_challenge_llm_service=ProjectChallengeLLMService(),  # type: ignore[arg-type]
    )

    challenge_step = next(step for step in result.state.steps if step.name == "ProjectInterviewAgent")
    assert challenge_step.mode == "llm"
    assert challenge_step.fallback_reason is None
    assert "LLM" in challenge_step.summary
    assert challenge_step.llm_success_count
    assert challenge_step.fallback_count == 0
    assert result.final_report.project_challenge_report.grounded_questions


def test_job_analysis_workflow_records_project_challenge_fallback_metadata() -> None:
    result = run_job_analysis_workflow(
        SAMPLE_RESUME,
        SAMPLE_JD,
        use_llm_project_challenge=True,
        project_challenge_llm_service=FailingLLMService(),  # type: ignore[arg-type]
    )

    challenge_step = next(step for step in result.state.steps if step.name == "ProjectInterviewAgent")
    assert challenge_step.mode == "fallback"
    assert challenge_step.fallback_reason == "LLMServiceError"
    assert "mock" in challenge_step.summary
    assert result.final_report.project_challenge_report.technical_deep_dive_questions
