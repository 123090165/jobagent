from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.jd_analysis_agent import analyze_jd
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ProjectChallengeReport, ResumeOptimizationResult
from app.schemas.report import FinalReport
from app.schemas.resume import ResumeProfile
from app.services.mock_pipeline import (
    mock_jd_analysis,
    mock_match_analysis,
    mock_project_challenge,
    mock_resume_optimization,
    mock_resume_parse,
)
from app.services.report_service import generate_markdown_report

WorkflowStepStatus = Literal["completed"]


class WorkflowStepTrace(BaseModel):
    name: str
    status: WorkflowStepStatus
    summary: str


class JobAnalysisWorkflowState(BaseModel):
    resume_text: str
    jd_text: str
    use_llm_jd: bool = False
    resume_profile: ResumeProfile | None = None
    job_analysis: JobAnalysis | None = None
    match_report: MatchReport | None = None
    optimization_result: ResumeOptimizationResult | None = None
    project_challenge_report: ProjectChallengeReport | None = None
    markdown_report: str | None = None
    steps: list[WorkflowStepTrace] = Field(default_factory=list)


class JobAnalysisWorkflowResult(BaseModel):
    final_report: FinalReport
    state: JobAnalysisWorkflowState


def run_job_analysis_workflow(
    resume_text: str,
    jd_text: str,
    *,
    use_llm_jd: bool = False,
) -> JobAnalysisWorkflowResult:
    """Run the explicit JobAgent analysis workflow with traceable steps."""
    normalized_resume = resume_text.strip()
    normalized_jd = jd_text.strip()

    if not normalized_resume:
        raise ValueError("resume_text cannot be empty")
    if not normalized_jd:
        raise ValueError("jd_text cannot be empty")

    state = JobAnalysisWorkflowState(
        resume_text=normalized_resume,
        jd_text=normalized_jd,
        use_llm_jd=use_llm_jd,
    )

    state.resume_profile = mock_resume_parse(normalized_resume)
    _record_step(
        state,
        "ResumeParseAgent",
        f"识别技能 {len(state.resume_profile.skills)} 个，项目 {len(state.resume_profile.projects)} 个。",
    )

    if use_llm_jd:
        state.job_analysis = analyze_jd(normalized_jd, use_llm=True)
        jd_summary = "使用 JDAnalysisAgent 请求 LLM；失败时由 Agent 内部回退 mock。"
    else:
        state.job_analysis = mock_jd_analysis(normalized_jd)
        jd_summary = "使用 mock JD 规则分析。"
    _record_step(
        state,
        "JDAnalysisAgent",
        f"{jd_summary} 必备技能 {len(state.job_analysis.required_skills)} 个。",
    )

    state.match_report = mock_match_analysis(state.resume_profile, state.job_analysis)
    _record_step(
        state,
        "MatchAgent",
        f"生成匹配报告，总分 {state.match_report.overall_score:.1f}。",
    )

    state.optimization_result = mock_resume_optimization(
        normalized_resume,
        state.resume_profile,
        state.job_analysis,
        state.match_report,
    )
    _record_step(
        state,
        "ResumeOptimizeAgent",
        f"生成 {len(state.optimization_result.jd_targeted_bullets)} 条 JD 定向建议。",
    )

    state.project_challenge_report = mock_project_challenge(
        state.resume_profile,
        state.job_analysis,
    )
    _record_step(
        state,
        "ProjectInterviewAgent",
        "生成项目追问和面试官关注点。",
    )

    state.markdown_report = generate_markdown_report(
        resume_profile=state.resume_profile,
        job_analysis=state.job_analysis,
        match_report=state.match_report,
        optimization_result=state.optimization_result,
        project_challenge_report=state.project_challenge_report,
    )
    _record_step(
        state,
        "ReportAgent",
        "聚合结构化结果并生成 Markdown 报告。",
    )

    final_report = FinalReport(
        resume_profile=state.resume_profile,
        job_analysis=state.job_analysis,
        match_report=state.match_report,
        optimization_result=state.optimization_result,
        project_challenge_report=state.project_challenge_report,
        markdown_report=state.markdown_report,
    )
    return JobAnalysisWorkflowResult(final_report=final_report, state=state)


def _record_step(
    state: JobAnalysisWorkflowState,
    name: str,
    summary: str,
) -> None:
    state.steps.append(
        WorkflowStepTrace(
            name=name,
            status="completed",
            summary=summary,
        )
    )
