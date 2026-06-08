from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.types import AgentExecutionMode, AgentRunMetadata, AgentRunResult
from app.schemas.job import JobAnalysis
from app.schemas.match import GroundedChallengeQuestion, MatchReport, ProjectChallengeReport
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
  "grounded_questions": [
    {
      "question": string,
      "linked_requirement": string,
      "match_level": string,
      "why_asked": string,
      "related_resume_evidence": string[],
      "expected_answer_points": string[],
      "risk_level": string
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
    match_report: MatchReport | None = None,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> ProjectChallengeReport:
    """Generate interview challenge questions from resume and JD context."""
    return run_project_challenge_agent(
        resume_profile,
        job_analysis,
        match_report=match_report,
        use_llm=use_llm,
        service=service,
    ).output


def run_project_challenge_agent(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport | None = None,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> AgentRunResult[ProjectChallengeReport]:
    """Generate interview challenge questions with metadata."""
    if not use_llm:
        return AgentRunResult(
            output=_with_grounded_questions(
                _mock_project_challenge(resume_profile, job_analysis),
                resume_profile,
                job_analysis,
                match_report,
            ),
            metadata=_metadata(mode="mock"),
        )

    try:
        return AgentRunResult(
            output=_with_grounded_questions(
                generate_project_challenge_with_llm(
                    resume_profile,
                    job_analysis,
                    service=service,
                ),
                resume_profile,
                job_analysis,
                match_report,
            ),
            metadata=_metadata(mode="llm"),
        )
    except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
        return AgentRunResult(
            output=_with_grounded_questions(
                _mock_project_challenge(resume_profile, job_analysis),
                resume_profile,
                job_analysis,
                match_report,
            ),
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


def _with_grounded_questions(
    result: ProjectChallengeReport,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport | None,
) -> ProjectChallengeReport:
    return result.model_copy(
        update={
            "grounded_questions": _build_grounded_challenge_questions(
                resume_profile,
                job_analysis,
                match_report,
            )
        }
    )


def _build_grounded_challenge_questions(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport | None,
) -> list[GroundedChallengeQuestion]:
    if match_report is None or not match_report.requirement_matches:
        return []

    del resume_profile
    del job_analysis

    ranked_matches = sorted(
        match_report.requirement_matches,
        key=lambda item: (_match_priority(item.match_level), _importance_priority(item.importance)),
    )
    grounded_questions: list[GroundedChallengeQuestion] = []
    for match in ranked_matches:
        grounded_questions.append(_build_grounded_question(match))
        if len(grounded_questions) >= 8:
            break
    return grounded_questions


def _build_grounded_question(match) -> GroundedChallengeQuestion:
    if match.match_level == "matched":
        evidence = match.resume_evidence[:2]
        return GroundedChallengeQuestion(
            question=(
                f"You have resume evidence for {match.requirement}. Walk through the specific project or work context, "
                "the key implementation choices, the tradeoffs you made, and the result."
            ),
            linked_requirement=match.requirement,
            match_level=match.match_level,
            why_asked="This requirement already looks matched, so the interviewer will validate depth and authenticity.",
            related_resume_evidence=evidence,
            expected_answer_points=[
                "personal ownership",
                "technical implementation details",
                "tradeoffs and constraints",
                "results or observable outcomes",
            ],
            risk_level="medium",
        )

    if match.match_level == "partial":
        evidence = match.resume_evidence[:2]
        return GroundedChallengeQuestion(
            question=(
                f"Your resume shows partial evidence for {match.requirement}. What exactly did you implement, "
                "what related pieces were missing from the resume wording, and how would you clarify the boundary in an interview?"
            ),
            linked_requirement=match.requirement,
            match_level=match.match_level,
            why_asked="This requirement is only partially matched, so the interviewer will probe the blurry part.",
            related_resume_evidence=evidence,
            expected_answer_points=[
                "what evidence already exists",
                "what detail is still missing",
                "how the experience maps to the JD requirement",
                "how to explain the boundary without overstating",
            ],
            risk_level="high",
        )

    return GroundedChallengeQuestion(
        question=(
            f"The JD asks for {match.requirement}, but your resume does not show direct evidence. "
            "If an interviewer asks about it, how would you give an honest answer about your experience boundary and your plan to close the gap?"
        ),
        linked_requirement=match.requirement,
        match_level=match.match_level,
        why_asked="This requirement is missing, so the best answer needs honest gap handling instead of invented experience.",
        related_resume_evidence=[],
        expected_answer_points=[
            "state the real experience boundary",
            "connect to adjacent skills or foundations",
            "describe a learning or project plan",
            "avoid unsupported claims",
        ],
        risk_level="high",
    )


def _match_priority(match_level: str) -> int:
    priorities = {"partial": 0, "matched": 1, "missing": 2}
    return priorities.get(match_level, 3)


def _importance_priority(importance: str) -> int:
    priorities = {"must": 0, "should": 1, "nice": 2}
    return priorities.get(importance, 3)


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
