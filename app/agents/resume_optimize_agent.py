from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agents.types import AgentExecutionMode, AgentRunMetadata, AgentRunResult
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ResumeOptimizationResult, RewriteSuggestion
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
  "rewrite_suggestions": [
    {
      "target_section": string,
      "linked_requirement": string,
      "match_level": string,
      "original_issue": string,
      "suggested_bullet": string,
      "reason": string,
      "evidence_source": string[]
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
            output=_with_rewrite_suggestions(
                _mock_resume_optimization(
                    normalized_resume,
                    resume_profile,
                    job_analysis,
                    match_report,
                ),
                resume_profile,
                job_analysis,
                match_report,
            ),
            metadata=_metadata(mode="mock"),
        )

    try:
        return AgentRunResult(
            output=_with_rewrite_suggestions(
                optimize_resume_with_llm(
                    normalized_resume,
                    resume_profile,
                    job_analysis,
                    match_report,
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
            output=_with_rewrite_suggestions(
                _mock_resume_optimization(
                    normalized_resume,
                    resume_profile,
                    job_analysis,
                    match_report,
                ),
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


def _with_rewrite_suggestions(
    result: ResumeOptimizationResult,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> ResumeOptimizationResult:
    return result.model_copy(
        update={
            "rewrite_suggestions": _build_rewrite_suggestions(
                resume_profile,
                job_analysis,
                match_report,
            )
        }
    )


def _build_rewrite_suggestions(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> list[RewriteSuggestion]:
    del resume_profile
    del job_analysis

    ranked_matches = sorted(
        match_report.requirement_matches,
        key=lambda item: (_match_priority(item.match_level), _importance_priority(item.importance)),
    )
    suggestions: list[RewriteSuggestion] = []
    for match in ranked_matches:
        suggestion = _build_rewrite_suggestion(match)
        if suggestion is None:
            continue
        suggestions.append(suggestion)
        if len(suggestions) >= 6:
            break
    return suggestions


def _build_rewrite_suggestion(match) -> RewriteSuggestion | None:
    if match.match_level in {"matched", "partial"} and match.resume_evidence:
        target_section = _infer_target_section(match.resume_evidence)
        suggested_bullet = _build_supported_bullet(
            requirement=match.requirement,
            evidence=match.resume_evidence[0],
            match_level=match.match_level,
        )
        original_issue = (
            f"Current evidence for {match.requirement} exists but is not yet framed as direct JD evidence."
            if match.match_level == "matched"
            else f"Current evidence for {match.requirement} is only partially aligned to the JD wording."
        )
        reason = (
            f"This rewrite keeps the claim grounded in existing resume evidence while making {match.requirement} easier to spot."
        )
        return RewriteSuggestion(
            target_section=target_section,
            linked_requirement=match.requirement,
            match_level=match.match_level,
            original_issue=original_issue,
            suggested_bullet=suggested_bullet,
            reason=reason,
            evidence_source=match.resume_evidence[:2],
            original=match.resume_evidence[0],
            suggestion=suggested_bullet,
        )

    if match.match_level == "missing":
        return RewriteSuggestion(
            target_section="skills",
            linked_requirement=match.requirement,
            match_level=match.match_level,
            original_issue=f"The resume does not currently show direct evidence for {match.requirement}.",
            suggested_bullet=(
                f"If you have real experience with {match.requirement}, add a truthful bullet describing where you used it. "
                "If not, keep this as a preparation gap instead of adding unsupported claims."
            ),
            reason="Missing requirements should stay explicit gaps unless the user has real supporting experience to add.",
            evidence_source=[],
            suggestion=(
                f"If you have real experience with {match.requirement}, add a truthful bullet describing where you used it."
            ),
        )

    return None


def _build_supported_bullet(
    *,
    requirement: str,
    evidence: str,
    match_level: str,
) -> str:
    cleaned_evidence = _strip_evidence_prefix(evidence)
    if evidence.startswith("Skill:"):
        return f"Core skill: {cleaned_evidence}, highlighted directly against the JD requirement for {requirement}."
    if _infer_target_section([evidence]) == "experience":
        prefix = "Strengthen this work bullet"
    elif _infer_target_section([evidence]) == "projects":
        prefix = "Strengthen this project bullet"
    else:
        prefix = "Strengthen this resume bullet"
    qualifier = (
        "to make the existing evidence read as a direct match"
        if match_level == "matched"
        else "to make the partial evidence read more directly against the JD"
    )
    return f"{prefix}: {cleaned_evidence}. Rephrase it {qualifier} for {requirement}."


def _infer_target_section(evidence_source: list[str]) -> str:
    if not evidence_source:
        return "summary"
    first_evidence = evidence_source[0]
    if first_evidence.startswith("Skill:"):
        return "skills"
    if first_evidence.startswith("Education:"):
        return "education"
    if first_evidence.startswith("Certificate:"):
        return "summary"
    if first_evidence.startswith("Highlight:"):
        return "summary"
    if first_evidence.startswith("Work") or first_evidence.startswith("Experience:"):
        return "experience"
    if "Technologies:" in first_evidence or "Highlights:" in first_evidence or " | " in first_evidence:
        return "projects"
    return "summary"


def _strip_evidence_prefix(evidence: str) -> str:
    cleaned = re.sub(r"^(Skill|Education|Certificate|Highlight|Experience):\s*", "", evidence).strip()
    return cleaned.replace("Work | ", "", 1)


def _match_priority(match_level: str) -> int:
    priorities = {"partial": 0, "missing": 1, "matched": 2}
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
