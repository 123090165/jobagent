from __future__ import annotations

from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.agents.jd_analysis_agent import run_jd_analysis_agent
from app.agents.match_agent import run_match_agent
from app.agents.project_challenge_agent import run_project_challenge_agent
from app.agents.report_agent import run_report_agent
from app.agents.resume_optimize_agent import run_resume_optimize_agent
from app.agents.resume_parse_agent import run_resume_parse_agent
from app.agents.types import AgentExecutionMode, AgentRunMetadata
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ProjectChallengeReport, ResumeOptimizationResult
from app.schemas.report import AnalysisQualityReport, FinalReport
from app.schemas.resume import ResumeProfile
from app.services.llm_service import LLMService
from app.services.report_service import build_analysis_quality_report

WorkflowStepStatus = Literal["completed"]


class WorkflowStepTrace(BaseModel):
    workflow_run_id: str
    name: str
    status: WorkflowStepStatus
    mode: AgentExecutionMode
    summary: str
    duration_ms: float = 0.0
    fallback_reason: str | None = None
    guardrails: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    llm_success_count: int | None = None
    fallback_count: int | None = None
    item_fallback_reasons: list[str] = Field(default_factory=list)
    prompt_version: str | None = None


class JobAnalysisWorkflowState(BaseModel):
    workflow_run_id: str = Field(default_factory=lambda: uuid4().hex)
    resume_text: str
    jd_text: str
    use_llm_jd: bool = False
    use_llm_resume_optimize: bool = False
    use_llm_project_challenge: bool = False
    resume_profile: ResumeProfile | None = None
    job_analysis: JobAnalysis | None = None
    match_report: MatchReport | None = None
    optimization_result: ResumeOptimizationResult | None = None
    project_challenge_report: ProjectChallengeReport | None = None
    analysis_quality: AnalysisQualityReport = Field(default_factory=AnalysisQualityReport)
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
    jd_llm_service: LLMService | None = None,
    use_llm_resume_optimize: bool = False,
    resume_optimize_llm_service: LLMService | None = None,
    use_llm_project_challenge: bool = False,
    project_challenge_llm_service: LLMService | None = None,
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
        use_llm_resume_optimize=use_llm_resume_optimize,
        use_llm_project_challenge=use_llm_project_challenge,
    )

    step_started_at = perf_counter()
    resume_result = run_resume_parse_agent(normalized_resume)
    state.resume_profile = resume_result.output
    _record_step(
        state,
        resume_result.metadata,
        f"识别技能 {len(state.resume_profile.skills)} 个，项目 {len(state.resume_profile.projects)} 个。",
        duration_ms=_elapsed_ms(step_started_at),
    )

    step_started_at = perf_counter()
    jd_result = run_jd_analysis_agent(
        normalized_jd,
        use_llm=use_llm_jd,
        service=jd_llm_service,
    )
    state.job_analysis = jd_result.output
    _record_step(
        state,
        jd_result.metadata,
        f"{_format_mode_summary(jd_result.metadata)} 必备技能 {len(state.job_analysis.required_skills)} 个。",
        duration_ms=_elapsed_ms(step_started_at),
    )

    step_started_at = perf_counter()
    match_result = run_match_agent(state.resume_profile, state.job_analysis)
    state.match_report = match_result.output
    _record_step(
        state,
        match_result.metadata,
        f"生成匹配报告，总分 {state.match_report.overall_score:.1f}。",
        duration_ms=_elapsed_ms(step_started_at),
    )

    step_started_at = perf_counter()
    optimization_result = run_resume_optimize_agent(
        normalized_resume,
        state.resume_profile,
        state.job_analysis,
        state.match_report,
        use_llm=use_llm_resume_optimize,
        service=resume_optimize_llm_service,
    )
    state.optimization_result = optimization_result.output
    _record_step(
        state,
        optimization_result.metadata,
        (
            f"{_format_resume_optimize_mode_summary(optimization_result.metadata)} "
            f"生成 {len(state.optimization_result.jd_targeted_bullets)} 条 JD 定向建议。"
        ),
        duration_ms=_elapsed_ms(step_started_at),
    )

    step_started_at = perf_counter()
    challenge_result = run_project_challenge_agent(
        state.resume_profile,
        state.job_analysis,
        match_report=state.match_report,
        use_llm=use_llm_project_challenge,
        service=project_challenge_llm_service,
    )
    state.project_challenge_report = challenge_result.output
    _record_step(
        state,
        challenge_result.metadata,
        _format_project_challenge_mode_summary(challenge_result.metadata),
        duration_ms=_elapsed_ms(step_started_at),
    )

    state.analysis_quality = build_analysis_quality_report(
        state.resume_profile,
        state.job_analysis,
        state.match_report,
    )

    step_started_at = perf_counter()
    report_result = run_report_agent(
        resume_profile=state.resume_profile,
        job_analysis=state.job_analysis,
        match_report=state.match_report,
        optimization_result=state.optimization_result,
        project_challenge_report=state.project_challenge_report,
    )
    state.markdown_report = report_result.output
    _record_step(
        state,
        report_result.metadata,
        "聚合结构化结果并生成 Markdown 报告。",
        duration_ms=_elapsed_ms(step_started_at),
    )

    final_report = FinalReport(
        resume_profile=state.resume_profile,
        job_analysis=state.job_analysis,
        match_report=state.match_report,
        optimization_result=state.optimization_result,
        project_challenge_report=state.project_challenge_report,
        analysis_quality=state.analysis_quality,
        markdown_report=state.markdown_report,
    )
    return JobAnalysisWorkflowResult(final_report=final_report, state=state)


def _record_step(
    state: JobAnalysisWorkflowState,
    metadata: AgentRunMetadata,
    summary: str,
    *,
    duration_ms: float,
) -> None:
    state.steps.append(
        WorkflowStepTrace(
            workflow_run_id=state.workflow_run_id,
            name=metadata.agent_name,
            status="completed",
            mode=metadata.mode,
            summary=summary,
            duration_ms=duration_ms,
            fallback_reason=metadata.fallback_reason,
            guardrails=metadata.guardrails,
            quality_warnings=metadata.quality_warnings,
            llm_success_count=metadata.llm_success_count,
            fallback_count=metadata.fallback_count,
            item_fallback_reasons=metadata.item_fallback_reasons,
            prompt_version=metadata.prompt_version,
        )
    )


def _format_mode_summary(metadata: AgentRunMetadata) -> str:
    if metadata.mode == "llm":
        return "使用 LLM JD 分析"
    if metadata.mode == "fallback":
        return f"LLM 分析失败，已回退 mock（{metadata.fallback_reason}）"
    return "使用 mock JD 规则分析"


def _format_resume_optimize_mode_summary(metadata: AgentRunMetadata) -> str:
    if metadata.mode == "llm":
        return "使用 LLM 简历优化"
    if metadata.mode == "fallback":
        return f"LLM 简历优化失败，已回退 mock（{metadata.fallback_reason}）"
    return "使用 mock 简历优化"


def _format_project_challenge_mode_summary(metadata: AgentRunMetadata) -> str:
    if metadata.mode == "llm":
        return "使用 LLM 项目追问"
    if metadata.mode == "fallback":
        return f"LLM 项目追问失败，已回退 mock（{metadata.fallback_reason}）"
    return "使用 mock 项目追问"


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
