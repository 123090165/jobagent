"""在确定性 JD 分析与可选 LLM 分析之间切换，并用质量门决定是否回退。"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.agents.types import AgentExecutionMode, AgentRunMetadata, AgentRunResult
from app.prompts.loader import load_prompt
from app.schemas.job import JobAnalysis
from app.services.jd_analysis_quality import evaluate_jd_analysis_quality
from app.services.jd_requirements import build_legacy_requirements, ground_requirements
from app.services.llm_service import LLMService, LLMServiceError


JD_ANALYSIS_PROMPT_VERSION = "jd_analysis_v3"
JD_ANALYSIS_SYSTEM_PROMPT = load_prompt("jd_analysis/system.md")


def analyze_jd(
    jd_text: str,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> JobAnalysis:
    """Analyze a JD with LLM when enabled, otherwise fall back to mock rules."""
    return run_jd_analysis_agent(
        jd_text,
        use_llm=use_llm,
        service=service,
    ).output


def run_jd_analysis_agent(
    jd_text: str,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> AgentRunResult[JobAnalysis]:
    """Analyze a JD and return execution metadata for workflow tracing."""
    normalized_jd = jd_text.strip()
    if not normalized_jd:
        raise ValueError("jd_text cannot be empty")

    if not use_llm:
        return AgentRunResult(
            output=_mock_jd_analysis(normalized_jd),
            metadata=_metadata(mode="mock"),
        )

    baseline = _mock_jd_analysis(normalized_jd)
    try:
        llm_output = analyze_jd_with_llm(normalized_jd, service=service)
        quality = evaluate_jd_analysis_quality(
            jd_text=normalized_jd,
            llm_analysis=llm_output,
            baseline_analysis=baseline,
        )
        if quality.fallback_recommended:
            return AgentRunResult(
                output=baseline,
                metadata=_metadata(
                    mode="fallback",
                    fallback_reason="quality_gate_failed",
                    quality_warnings=quality.warnings,
                ),
            )
        return AgentRunResult(
            output=llm_output,
            metadata=_metadata(mode="llm", quality_warnings=quality.warnings),
        )
    except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
        return AgentRunResult(
            output=baseline,
            metadata=_metadata(
                mode="fallback",
                fallback_reason=type(exc).__name__,
            ),
        )


def analyze_jd_with_llm(jd_text: str, *, service: LLMService | None = None) -> JobAnalysis:
    """Analyze a JD using an OpenAI-compatible LLM and validate the output."""
    llm_service = service or LLMService()
    payload = llm_service.chat_completion_json(
        system_prompt=JD_ANALYSIS_SYSTEM_PROMPT,
        user_prompt=f"Job description:\n\n{jd_text}",
    )
    return _validate_job_analysis(payload, raw_jd=jd_text)


def _validate_job_analysis(payload: dict[str, Any], *, raw_jd: str) -> JobAnalysis:
    normalized = dict(payload)
    normalized["raw_jd"] = raw_jd
    for field in [
        "responsibilities",
        "required_skills",
        "preferred_skills",
        "experience_requirements",
        "education_requirements",
        "soft_skills",
        "implicit_requirements",
        "keywords",
        "requirements",
    ]:
        normalized.setdefault(field, [])
    analysis = JobAnalysis.model_validate(normalized)
    requirements = analysis.requirements or build_legacy_requirements(
        raw_jd=raw_jd,
        required_skills=analysis.required_skills,
        preferred_skills=analysis.preferred_skills,
        experience_requirements=analysis.experience_requirements,
        education_requirements=analysis.education_requirements,
    )
    return analysis.model_copy(
        update={"requirements": ground_requirements(raw_jd, requirements)}
    )


def _mock_jd_analysis(jd_text: str) -> JobAnalysis:
    from app.services.mock_pipeline import mock_jd_analysis

    return mock_jd_analysis(jd_text)


def _metadata(
    *,
    mode: AgentExecutionMode,
    fallback_reason: str | None = None,
    quality_warnings: list[str] | None = None,
) -> AgentRunMetadata:
    return AgentRunMetadata(
        agent_name="JDAnalysisAgent",
        mode=mode,
        fallback_reason=fallback_reason,
        quality_warnings=quality_warnings or [],
        guardrails=[
            "不编造 JD 中不存在的信息",
            "不把加分项误判为必备项",
            "LLM 输出必须通过 JobAnalysis schema 校验",
            "LLM JD 分析输出必须通过质量门禁",
            f"prompt_version={JD_ANALYSIS_PROMPT_VERSION}",
        ],
    )
