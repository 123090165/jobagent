from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.types import AgentExecutionMode, AgentRunMetadata, AgentRunResult
from app.schemas.job import JobAnalysis
from app.schemas.match import ProjectChallengeReport
from app.schemas.resume import ResumeProfile
from app.services.llm_service import LLMService, LLMServiceError


PROJECT_CHALLENGE_SYSTEM_PROMPT = """You are JobAgent's ProjectChallengeAgent.

Task:
Generate one JSON object that matches this shape:
{
  "basic_questions": [
    {
      "question": string,
      "evaluates": string,
      "answer_framework": string
    }
  ],
  "technical_deep_dive_questions": [
    {
      "question": string,
      "evaluates": string,
      "answer_framework": string
    }
  ],
  "architecture_questions": [
    {
      "question": string,
      "evaluates": string,
      "answer_framework": string
    }
  ],
  "tradeoff_questions": [
    {
      "question": string,
      "evaluates": string,
      "answer_framework": string
    }
  ],
  "interviewer_concerns": string[],
  "improvement_suggestions": string[]
}

Rules:
- Only use information from ResumeProfile and JobAnalysis.
- Do not ask about projects that are not present in the resume.
- Do not assume the user has experience with companies, internships, projects, or technologies not provided.
- Do not invent project background, metrics, numbers, results, or tech stacks.
- You may ask realistic interview follow-up questions about existing projects, technical details, architecture, tradeoffs, risks, and improvements.
- Questions should be specific, concrete, and suitable for a real interview.
- If information is missing, keep lists short and focus on clarifying what is actually present.
- Return JSON only. No Markdown.
"""


def generate_project_challenges(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> ProjectChallengeReport:
    """Generate interview challenge questions from resume and JD context."""
    return run_project_challenge_agent(
        resume_profile,
        job_analysis,
        use_llm=use_llm,
        service=service,
    ).output


def run_project_challenge_agent(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> AgentRunResult[ProjectChallengeReport]:
    """Generate interview challenge questions with metadata."""
    if not use_llm:
        return AgentRunResult(
            output=_mock_project_challenge(resume_profile, job_analysis),
            metadata=_metadata(mode="mock"),
        )

    try:
        return AgentRunResult(
            output=generate_project_challenge_with_llm(
                resume_profile,
                job_analysis,
                service=service,
            ),
            metadata=_metadata(mode="llm"),
        )
    except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
        return AgentRunResult(
            output=_mock_project_challenge(resume_profile, job_analysis),
            metadata=_metadata(
                mode="fallback",
                fallback_reason=type(exc).__name__,
            ),
        )


def generate_project_challenge_with_llm(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    *,
    service: LLMService | None = None,
) -> ProjectChallengeReport:
    """Generate interview challenge questions with an LLM and validate output."""
    llm_service = service or LLMService()
    payload = llm_service.chat_completion_json(
        system_prompt=PROJECT_CHALLENGE_SYSTEM_PROMPT,
        user_prompt=(
            "ResumeProfile JSON:\n"
            f"{json.dumps(resume_profile.model_dump(), ensure_ascii=False)}\n\n"
            "JobAnalysis JSON:\n"
            f"{json.dumps(job_analysis.model_dump(), ensure_ascii=False)}"
        ),
    )
    return _validate_project_challenge(payload)


def _validate_project_challenge(payload: dict[str, Any]) -> ProjectChallengeReport:
    if not isinstance(payload, dict):
        raise TypeError("LLM project challenge output must be a JSON object")
    return ProjectChallengeReport.model_validate(payload)


def _mock_project_challenge(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> ProjectChallengeReport:
    from app.services.mock_pipeline import mock_project_challenge

    return mock_project_challenge(resume_profile, job_analysis)


def _metadata(
    *,
    mode: AgentExecutionMode,
    fallback_reason: str | None = None,
) -> AgentRunMetadata:
    return AgentRunMetadata(
        agent_name="ProjectInterviewAgent",
        mode=mode,
        fallback_reason=fallback_reason,
        guardrails=[
            "追问必须基于简历项目和目标 JD",
            "不追问简历里不存在的项目、公司或技术栈",
            "不编造项目背景、数据、指标或技术栈",
            "暴露短板时给出可执行补强方向",
            "LLM 输出必须通过 ProjectChallengeReport schema 校验",
        ],
    )
