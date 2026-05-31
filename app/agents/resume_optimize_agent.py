from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.types import AgentExecutionMode, AgentRunMetadata, AgentRunResult
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ResumeOptimizationResult
from app.schemas.resume import ResumeProfile
from app.services.llm_service import LLMService, LLMServiceError


RESUME_OPTIMIZE_SYSTEM_PROMPT = """You are JobAgent's ResumeOptimizeAgent.

Task:
Generate resume optimization suggestions and return one JSON object that matches this shape:
{
  "overall_issues": string[],
  "keywords_to_add": string[],
  "skills_section_suggestions": string[],
  "project_rewrite_suggestions": [
    {
      "original": string,
      "suggestion": string,
      "reason": string
    }
  ],
  "jd_targeted_bullets": string[],
  "do_not_exaggerate": string[],
  "missing_info_needed": string[]
}

Safety rules:
- Do not invent experiences the user did not provide.
- Do not invent companies, roles, projects, metrics, data, technologies, or tech stacks.
- Do not invent quantified outcomes.
- If a resume lacks metrics, only suggest that the user should add real metrics.
- Every suggestion must be based on the original resume, ResumeProfile, JobAnalysis, or MatchReport.
- You may rewrite wording and structure, but you must not add new facts.
- Keep suggestions actionable and interview-safe.
- Return JSON only. No Markdown.
"""


def optimize_resume(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> ResumeOptimizationResult:
    """Generate resume optimization suggestions without inventing experience."""
    return run_resume_optimize_agent(
        resume_text,
        resume_profile,
        job_analysis,
        match_report,
        use_llm=use_llm,
        service=service,
    ).output


def run_resume_optimize_agent(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> AgentRunResult[ResumeOptimizationResult]:
    """Generate resume optimization suggestions with safety metadata."""
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise ValueError("resume_text cannot be empty")

    if not use_llm:
        return AgentRunResult(
            output=_mock_resume_optimization(
                normalized_resume,
                resume_profile,
                job_analysis,
                match_report,
            ),
            metadata=_metadata(mode="mock"),
        )

    try:
        return AgentRunResult(
            output=optimize_resume_with_llm(
                normalized_resume,
                resume_profile,
                job_analysis,
                match_report,
                service=service,
            ),
            metadata=_metadata(mode="llm"),
        )
    except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
        return AgentRunResult(
            output=_mock_resume_optimization(
                normalized_resume,
                resume_profile,
                job_analysis,
                match_report,
            ),
            metadata=_metadata(
                mode="fallback",
                fallback_reason=type(exc).__name__,
            ),
        )


def optimize_resume_with_llm(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    *,
    service: LLMService | None = None,
) -> ResumeOptimizationResult:
    """Generate resume optimization suggestions with an LLM and validate output."""
    llm_service = service or LLMService()
    payload = llm_service.chat_completion_json(
        system_prompt=RESUME_OPTIMIZE_SYSTEM_PROMPT,
        user_prompt=(
            "Original resume text:\n"
            f"{resume_text}\n\n"
            "ResumeProfile JSON:\n"
            f"{json.dumps(resume_profile.model_dump(), ensure_ascii=False)}\n\n"
            "JobAnalysis JSON:\n"
            f"{json.dumps(job_analysis.model_dump(), ensure_ascii=False)}\n\n"
            "MatchReport JSON:\n"
            f"{json.dumps(match_report.model_dump(), ensure_ascii=False)}"
        ),
    )
    return _validate_resume_optimization(payload)


def _validate_resume_optimization(payload: dict[str, Any]) -> ResumeOptimizationResult:
    if not isinstance(payload, dict):
        raise TypeError("LLM resume optimization output must be a JSON object")
    return ResumeOptimizationResult.model_validate(payload)


def _mock_resume_optimization(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> ResumeOptimizationResult:
    from app.services.mock_pipeline import mock_resume_optimization

    return mock_resume_optimization(
        resume_text,
        resume_profile,
        job_analysis,
        match_report,
    )


def _metadata(
    *,
    mode: AgentExecutionMode,
    fallback_reason: str | None = None,
) -> AgentRunMetadata:
    return AgentRunMetadata(
        agent_name="ResumeOptimizeAgent",
        mode=mode,
        fallback_reason=fallback_reason,
        guardrails=[
            "不编造经历、公司、项目、数据或技术栈",
            "需要量化但缺少数据时只提示补充",
            "不覆盖原始简历文本",
            "LLM 输出必须通过 ResumeOptimizationResult schema 校验",
            "所有建议必须可追溯到简历或 JD",
        ],
    )
