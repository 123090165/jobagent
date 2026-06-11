from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.schemas import GeneratedGroundedQuestionDraft
from app.agents.types import AgentExecutionMode, AgentRunMetadata, AgentRunResult
from app.schemas.job import JobAnalysis
from app.schemas.match import ChallengeQuestion, GroundedChallengeQuestion, MatchReport, ProjectChallengeReport
from app.schemas.resume import ResumeProfile
from app.services.llm_service import LLMService, LLMServiceError
from app.services.project_challenge_planner import ChallengeRequirement, select_challenge_requirements
from app.services.project_question_generation import (
    PROJECT_QUESTION_GENERATOR_PROMPT_VERSION,
    generate_grounded_question_with_llm,
)


PROJECT_CHALLENGE_SYSTEM_PROMPT = """You are JobAgent's ProjectChallengeAgent.

Task:
Generate one JSON object that matches the existing ProjectChallengeReport schema.

Rules:
- Only use information from ResumeProfile and JobAnalysis.
- Do not ask about projects that are not present in the resume.
- Do not assume the user has experience with companies, internships, projects, or technologies not provided.
- Do not invent project background, metrics, numbers, results, or tech stacks.
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
    """Generate project interview challenges with per-question LLM fallback."""
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
        selected_requirements = (
            select_challenge_requirements(
                resume_profile=resume_profile,
                job_analysis=job_analysis,
                match_report=match_report,
            )
            if match_report is not None
            else []
        )
    except (ValueError, TypeError) as exc:
        return _whole_report_fallback(
            resume_profile,
            job_analysis,
            match_report,
            fallback_reason=type(exc).__name__,
            fallback_count=0,
            llm_success_count=0,
        )

    if not selected_requirements:
        return _whole_report_fallback(
            resume_profile,
            job_analysis,
            match_report,
            fallback_reason="NoChallengeRequirements",
            fallback_count=0,
            llm_success_count=0,
        )

    llm_service = service or LLMService()
    generated_items: list[tuple[ChallengeRequirement, GeneratedGroundedQuestionDraft]] = []
    item_fallback_reasons: list[str] = []
    llm_success_count = 0
    fallback_count = 0

    for requirement in selected_requirements:
        try:
            generated = generate_grounded_question_with_llm(
                llm_service=llm_service,
                requirement=requirement,
                job_title=job_analysis.job_title,
                job_category=job_analysis.job_category,
            )
            llm_success_count += 1
        except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
            generated = build_fallback_grounded_question(requirement)
            fallback_count += 1
            item_fallback_reasons.append(f"{requirement.requirement}: {type(exc).__name__}")
        generated_items.append((requirement, generated))

    if llm_success_count == 0:
        fallback_reason = item_fallback_reasons[0].split(": ", 1)[-1] if item_fallback_reasons else "LLMServiceError"
        return _whole_report_fallback(
            resume_profile,
            job_analysis,
            match_report,
            fallback_reason=fallback_reason,
            fallback_count=fallback_count,
            llm_success_count=llm_success_count,
            item_fallback_reasons=item_fallback_reasons,
        )

    return AgentRunResult(
        output=_assemble_project_challenge_report(generated_items),
        metadata=_metadata(
            mode="llm",
            fallback_count=fallback_count,
            llm_success_count=llm_success_count,
            item_fallback_reasons=item_fallback_reasons,
            prompt_version=PROJECT_QUESTION_GENERATOR_PROMPT_VERSION,
        ),
    )


def generate_project_challenge_with_llm(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    *,
    service: LLMService | None = None,
) -> ProjectChallengeReport:
    """Generate a legacy full report with an LLM and validate output.

    The agent workflow now uses small-step question generation. This helper is
    retained for direct callers that still validate full ProjectChallengeReport payloads.
    """
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


def build_fallback_grounded_question(requirement: ChallengeRequirement) -> GeneratedGroundedQuestionDraft:
    """Build one deterministic grounded question for a selected requirement."""
    if requirement.match_level == "matched":
        return GeneratedGroundedQuestionDraft(
            question=(
                f"You listed evidence related to {requirement.requirement}. Can you explain how you used it "
                "in the project and what design decision you made?"
            ),
            why_asked="The resume already has related evidence, so the interviewer will validate depth and ownership.",
            expected_answer_points=[
                "where the evidence appears in the project or work context",
                "what implementation choice the candidate personally made",
                "what tradeoff or constraint shaped the decision",
            ],
            risk_level="medium",
            question_type="technical",
        )

    if requirement.match_level == "partial":
        return GeneratedGroundedQuestionDraft(
            question=(
                f"Your resume partially matches {requirement.requirement}. Which part have you actually implemented, "
                "and what would you still need to learn?"
            ),
            why_asked="The evidence is related but incomplete, so the interviewer will probe the real boundary.",
            expected_answer_points=[
                "which part has been implemented",
                "which part is adjacent but not yet demonstrated",
                "how the candidate would close the gap honestly",
            ],
            risk_level="medium",
            question_type="basic",
        )

    return GeneratedGroundedQuestionDraft(
        question=(
            f"This role expects {requirement.requirement}, but your resume does not show strong evidence. "
            "How would you approach learning or demonstrating it before the interview?"
        ),
        why_asked="The JD requirement is important but the resume lacks direct evidence.",
        expected_answer_points=[
            "state the current experience boundary",
            "connect to adjacent skills if real evidence exists",
            "describe a concrete preparation or demonstration plan",
        ],
        risk_level="high",
        question_type="basic",
    )


def _assemble_project_challenge_report(
    items: list[tuple[ChallengeRequirement, GeneratedGroundedQuestionDraft]],
) -> ProjectChallengeReport:
    report = ProjectChallengeReport()
    for requirement, generated in items:
        question = ChallengeQuestion(
            question=generated.question,
            evaluates=generated.why_asked,
            answer_framework="; ".join(generated.expected_answer_points),
        )
        if generated.question_type == "basic":
            report.basic_questions.append(question)
        elif generated.question_type == "technical":
            report.technical_deep_dive_questions.append(question)
        elif generated.question_type == "architecture":
            report.architecture_questions.append(question)
        else:
            report.tradeoff_questions.append(question)

        report.grounded_questions.append(
            GroundedChallengeQuestion(
                question=generated.question,
                linked_requirement=requirement.requirement,
                match_level=requirement.match_level,
                why_asked=generated.why_asked,
                related_resume_evidence=requirement.related_resume_evidence,
                expected_answer_points=generated.expected_answer_points,
                risk_level=generated.risk_level,
            )
        )

    report.interviewer_concerns = _build_interviewer_concerns(items)
    report.improvement_suggestions = _build_improvement_suggestions(items)
    return report


def _whole_report_fallback(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport | None,
    *,
    fallback_reason: str,
    fallback_count: int | None,
    llm_success_count: int | None,
    item_fallback_reasons: list[str] | None = None,
) -> AgentRunResult[ProjectChallengeReport]:
    return AgentRunResult(
        output=_with_grounded_questions(
            _mock_project_challenge(resume_profile, job_analysis),
            resume_profile,
            job_analysis,
            match_report,
        ),
        metadata=_metadata(
            mode="fallback",
            fallback_reason=fallback_reason,
            fallback_count=fallback_count,
            llm_success_count=llm_success_count,
            item_fallback_reasons=item_fallback_reasons or [],
            prompt_version=PROJECT_QUESTION_GENERATOR_PROMPT_VERSION,
        ),
    )


def _build_interviewer_concerns(
    items: list[tuple[ChallengeRequirement, GeneratedGroundedQuestionDraft]],
) -> list[str]:
    concerns: list[str] = []
    if any(requirement.match_level == "partial" for requirement, _ in items):
        concerns.append("Some JD requirements are only partially supported, so interviewers may probe exact scope.")
    if any(requirement.match_level == "missing" for requirement, _ in items):
        concerns.append("Some expected requirements lack direct resume evidence and should be handled as preparation gaps.")
    if any(not requirement.related_resume_evidence for requirement, _ in items):
        concerns.append("At least one question has weak resume evidence, so answers should avoid unsupported claims.")
    return concerns[:3]


def _build_improvement_suggestions(
    items: list[tuple[ChallengeRequirement, GeneratedGroundedQuestionDraft]],
) -> list[str]:
    suggestions: list[str] = []
    for requirement, _ in items:
        if requirement.match_level in {"matched", "partial"} and requirement.related_resume_evidence:
            suggestions.append(f"Prepare a concrete project walkthrough for {requirement.requirement}.")
        elif requirement.match_level == "missing":
            suggestions.append(f"Prepare an honest learning or demo plan for {requirement.requirement}.")
        if len(suggestions) >= 3:
            break
    return suggestions


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
    fallback_count: int | None = None,
    llm_success_count: int | None = None,
    item_fallback_reasons: list[str] | None = None,
    prompt_version: str | None = None,
) -> AgentRunMetadata:
    return AgentRunMetadata(
        agent_name="ProjectInterviewAgent",
        mode=mode,
        fallback_reason=fallback_reason,
        guardrails=[
            "Questions must be grounded in resume projects and the target JD.",
            "Do not ask about projects, companies, or tech stacks absent from the resume.",
            "Do not invent project background, metrics, or achievements.",
            "Expose gaps with actionable preparation directions.",
            "LLM output must pass the small GeneratedGroundedQuestionDraft schema.",
        ],
        llm_success_count=llm_success_count,
        fallback_count=fallback_count,
        item_fallback_reasons=item_fallback_reasons or [],
        prompt_version=prompt_version,
    )
