from __future__ import annotations

import pytest

from app.services.llm_service import LLMServiceError
from app.services.mock_pipeline import run_mock_pipeline
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


class FailingLLMService:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str):
        raise LLMServiceError("fake workflow failure")


def test_job_analysis_workflow_records_step_trace() -> None:
    result = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    assert result.final_report.markdown_report
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
    assert "回退 mock" in jd_step.summary
    assert result.final_report.job_analysis.required_skills
