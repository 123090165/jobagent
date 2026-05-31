from __future__ import annotations

from time import perf_counter
from typing import Literal, TypedDict
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
from app.schemas.report import FinalReport
from app.schemas.resume import ResumeProfile
from app.services.llm_service import LLMService
from app.services.mock_pipeline import mock_project_challenge, mock_resume_optimization
from app.workflows.job_analysis_workflow import WorkflowStepTrace

RouteDecision = Literal["low_match_prepare", "resume_optimize"]


class LangGraphJobAnalysisWorkflowState(BaseModel):
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
    markdown_report: str | None = None
    steps: list[WorkflowStepTrace] = Field(default_factory=list)
    route_decision: RouteDecision | None = None


class LangGraphJobAnalysisWorkflowResult(BaseModel):
    final_report: FinalReport
    state: LangGraphJobAnalysisWorkflowState


class _GraphState(TypedDict, total=False):
    workflow_run_id: str
    resume_text: str
    jd_text: str
    use_llm_jd: bool
    use_llm_resume_optimize: bool
    use_llm_project_challenge: bool
    resume_profile: ResumeProfile
    job_analysis: JobAnalysis
    match_report: MatchReport
    optimization_result: ResumeOptimizationResult
    project_challenge_report: ProjectChallengeReport
    markdown_report: str
    steps: list[WorkflowStepTrace]
    route_decision: RouteDecision


def run_langgraph_job_analysis_workflow(
    resume_text: str,
    jd_text: str,
    *,
    use_llm_jd: bool = False,
    jd_llm_service: LLMService | None = None,
    use_llm_resume_optimize: bool = False,
    resume_optimize_llm_service: LLMService | None = None,
    use_llm_project_challenge: bool = False,
    project_challenge_llm_service: LLMService | None = None,
) -> LangGraphJobAnalysisWorkflowResult:
    """Run the LangGraph workflow prototype without replacing the default workflow."""
    StateGraph = _load_state_graph()

    normalized_resume = resume_text.strip()
    normalized_jd = jd_text.strip()

    if not normalized_resume:
        raise ValueError("resume_text cannot be empty")
    if not normalized_jd:
        raise ValueError("jd_text cannot be empty")

    def resume_parse_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        result = run_resume_parse_agent(state["resume_text"])
        resume_profile = result.output
        return {
            "resume_profile": resume_profile,
            "steps": _append_step(
                state,
                _step_from_metadata(
                    state["workflow_run_id"],
                    result.metadata,
                    summary=(
                        "Parsed resume text into ResumeProfile with "
                        f"{len(resume_profile.skills)} skills and {len(resume_profile.projects)} projects."
                    ),
                    duration_ms=_elapsed_ms(started_at),
                ),
            ),
        }

    def jd_analysis_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        result = run_jd_analysis_agent(
            state["jd_text"],
            use_llm=state["use_llm_jd"],
            service=jd_llm_service,
        )
        job_analysis = result.output
        return {
            "job_analysis": job_analysis,
            "steps": _append_step(
                state,
                _step_from_metadata(
                    state["workflow_run_id"],
                    result.metadata,
                    summary=(
                        f"{_format_jd_mode_summary(result.metadata)} "
                        f"Extracted {len(job_analysis.required_skills)} required skills."
                    ),
                    duration_ms=_elapsed_ms(started_at),
                ),
            ),
        }

    def match_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        result = run_match_agent(state["resume_profile"], state["job_analysis"])
        match_report = result.output
        return {
            "match_report": match_report,
            "steps": _append_step(
                state,
                _step_from_metadata(
                    state["workflow_run_id"],
                    result.metadata,
                    summary=f"Generated match report with overall score {match_report.overall_score:.1f}.",
                    duration_ms=_elapsed_ms(started_at),
                ),
            ),
        }

    def route_by_match_score(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        overall_score = state["match_report"].overall_score
        if overall_score < 50:
            decision: RouteDecision = "low_match_prepare"
            summary = (
                f"Overall score {overall_score:.1f} is below 50. "
                "Route to low-match preparation before final report."
            )
        else:
            decision = "resume_optimize"
            summary = (
                f"Overall score {overall_score:.1f} meets the threshold. "
                "Route to resume optimization and project challenge path."
            )

        return {
            "route_decision": decision,
            "steps": _append_step(
                state,
                _manual_step(
                    state["workflow_run_id"],
                    name="MatchScoreRouter",
                    mode="mock",
                    summary=summary,
                    duration_ms=_elapsed_ms(started_at),
                    guardrails=[
                        "Route by deterministic score threshold only.",
                        "Do not claim LLM optimization ran when the workflow intentionally skipped it.",
                    ],
                ),
            ),
        }

    def low_match_prepare_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        optimization_result = mock_resume_optimization(
            state["resume_text"],
            state["resume_profile"],
            state["job_analysis"],
            state["match_report"],
        )
        challenge_report = mock_project_challenge(
            state["resume_profile"],
            state["job_analysis"],
        )
        return {
            "optimization_result": optimization_result,
            "project_challenge_report": challenge_report,
            "steps": _append_step(
                state,
                _manual_step(
                    state["workflow_run_id"],
                    name="LowMatchPreparation",
                    mode="mock",
                    summary=(
                        "Prepared mock optimization and interview artifacts for low-match "
                        "report compatibility after skipping the standard enhancement path."
                    ),
                    duration_ms=_elapsed_ms(started_at),
                    guardrails=[
                        "Keep FinalReport schema compatible without forcing the standard path.",
                        "Mark this as low-match preparation instead of LLM resume optimization.",
                    ],
                ),
            ),
        }

    def resume_optimize_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        result = run_resume_optimize_agent(
            state["resume_text"],
            state["resume_profile"],
            state["job_analysis"],
            state["match_report"],
            use_llm=state["use_llm_resume_optimize"],
            service=resume_optimize_llm_service,
        )
        optimization_result = result.output
        return {
            "optimization_result": optimization_result,
            "steps": _append_step(
                state,
                _step_from_metadata(
                    state["workflow_run_id"],
                    result.metadata,
                    summary=(
                        f"{_format_resume_optimize_mode_summary(result.metadata)} "
                        f"Generated {len(optimization_result.jd_targeted_bullets)} JD-targeted bullets."
                    ),
                    duration_ms=_elapsed_ms(started_at),
                ),
            ),
        }

    def project_challenge_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        result = run_project_challenge_agent(
            state["resume_profile"],
            state["job_analysis"],
            use_llm=state["use_llm_project_challenge"],
            service=project_challenge_llm_service,
        )
        challenge_report = result.output
        return {
            "project_challenge_report": challenge_report,
            "steps": _append_step(
                state,
                _step_from_metadata(
                    state["workflow_run_id"],
                    result.metadata,
                    summary=(
                        f"{_format_project_challenge_mode_summary(result.metadata)} "
                        f"Generated {len(challenge_report.technical_deep_dive_questions)} technical deep-dive questions."
                    ),
                    duration_ms=_elapsed_ms(started_at),
                ),
            ),
        }

    def report_node(state: _GraphState) -> _GraphState:
        started_at = perf_counter()
        result = run_report_agent(
            resume_profile=state["resume_profile"],
            job_analysis=state["job_analysis"],
            match_report=state["match_report"],
            optimization_result=state["optimization_result"],
            project_challenge_report=state["project_challenge_report"],
        )
        summary = "Generated final Markdown report."
        if state.get("route_decision") == "low_match_prepare":
            summary = "Generated final Markdown report after low-match preparation."

        return {
            "markdown_report": result.output,
            "steps": _append_step(
                state,
                _step_from_metadata(
                    state["workflow_run_id"],
                    result.metadata,
                    summary=summary,
                    duration_ms=_elapsed_ms(started_at),
                ),
            ),
        }

    def next_node_after_routing(state: _GraphState) -> RouteDecision:
        return state["route_decision"]

    builder = StateGraph(_GraphState)
    builder.add_node("resume_parse", resume_parse_node)
    builder.add_node("jd_analysis", jd_analysis_node)
    builder.add_node("match", match_node)
    builder.add_node("route_by_match_score", route_by_match_score)
    builder.add_node("low_match_prepare", low_match_prepare_node)
    builder.add_node("resume_optimize", resume_optimize_node)
    builder.add_node("project_challenge", project_challenge_node)
    builder.add_node("report", report_node)

    builder.set_entry_point("resume_parse")
    builder.add_edge("resume_parse", "jd_analysis")
    builder.add_edge("jd_analysis", "match")
    builder.add_edge("match", "route_by_match_score")
    builder.add_conditional_edges("route_by_match_score", next_node_after_routing)
    builder.add_edge("low_match_prepare", "report")
    builder.add_edge("resume_optimize", "project_challenge")
    builder.add_edge("project_challenge", "report")
    builder.set_finish_point("report")

    graph = builder.compile()
    final_state_data = graph.invoke(
        {
            "workflow_run_id": uuid4().hex,
            "resume_text": normalized_resume,
            "jd_text": normalized_jd,
            "use_llm_jd": use_llm_jd,
            "use_llm_resume_optimize": use_llm_resume_optimize,
            "use_llm_project_challenge": use_llm_project_challenge,
            "steps": [],
        }
    )
    state = LangGraphJobAnalysisWorkflowState.model_validate(final_state_data)
    final_report = FinalReport(
        resume_profile=state.resume_profile,
        job_analysis=state.job_analysis,
        match_report=state.match_report,
        optimization_result=state.optimization_result,
        project_challenge_report=state.project_challenge_report,
        markdown_report=state.markdown_report,
    )
    return LangGraphJobAnalysisWorkflowResult(final_report=final_report, state=state)


def _load_state_graph():
    try:
        from langgraph.graph import StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph is not installed. Add 'langgraph' to the environment before "
            "running the LangGraph workflow prototype."
        ) from exc

    return StateGraph


def _append_step(state: _GraphState, step: WorkflowStepTrace) -> list[WorkflowStepTrace]:
    return [*state.get("steps", []), step]


def _step_from_metadata(
    workflow_run_id: str,
    metadata: AgentRunMetadata,
    *,
    summary: str,
    duration_ms: float,
) -> WorkflowStepTrace:
    return WorkflowStepTrace(
        workflow_run_id=workflow_run_id,
        name=metadata.agent_name,
        status="completed",
        mode=metadata.mode,
        summary=summary,
        duration_ms=duration_ms,
        fallback_reason=metadata.fallback_reason,
        guardrails=metadata.guardrails,
    )


def _manual_step(
    workflow_run_id: str,
    *,
    name: str,
    mode: AgentExecutionMode,
    summary: str,
    duration_ms: float,
    guardrails: list[str],
) -> WorkflowStepTrace:
    return WorkflowStepTrace(
        workflow_run_id=workflow_run_id,
        name=name,
        status="completed",
        mode=mode,
        summary=summary,
        duration_ms=duration_ms,
        guardrails=guardrails,
    )


def _format_jd_mode_summary(metadata: AgentRunMetadata) -> str:
    if metadata.mode == "llm":
        return "Used LLM JD analysis."
    if metadata.mode == "fallback":
        return f"JD analysis fell back to mock ({metadata.fallback_reason})."
    return "Used mock JD analysis."


def _format_resume_optimize_mode_summary(metadata: AgentRunMetadata) -> str:
    if metadata.mode == "llm":
        return "Used LLM resume optimization."
    if metadata.mode == "fallback":
        return f"Resume optimization fell back to mock ({metadata.fallback_reason})."
    return "Used mock resume optimization."


def _format_project_challenge_mode_summary(metadata: AgentRunMetadata) -> str:
    if metadata.mode == "llm":
        return "Used LLM project challenge generation."
    if metadata.mode == "fallback":
        return f"Project challenge generation fell back to mock ({metadata.fallback_reason})."
    return "Used mock project challenge generation."


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
