from __future__ import annotations

import pytest

from app.services.mock_pipeline import run_mock_pipeline
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


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


def test_mock_pipeline_delegates_to_workflow_without_changing_contract() -> None:
    pipeline_report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)
    workflow_report = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD).final_report

    assert pipeline_report.model_dump() == workflow_report.model_dump()


def test_job_analysis_workflow_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        run_job_analysis_workflow("", SAMPLE_JD)

    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        run_job_analysis_workflow(SAMPLE_RESUME, "")
