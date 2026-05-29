from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.schemas.job import JobAnalysis
from app.services.llm_service import LLMService, LLMServiceError


JD_ANALYSIS_SYSTEM_PROMPT = """You are JobAgent's JDAnalysisAgent.

Task:
Analyze a job description and return one JSON object that matches this shape:
{
  "raw_jd": string,
  "job_title": string or null,
  "company": string or null,
  "location": string or null,
  "responsibilities": string[],
  "required_skills": string[],
  "preferred_skills": string[],
  "experience_requirements": string[],
  "education_requirements": string[],
  "soft_skills": string[],
  "implicit_requirements": string[],
  "keywords": string[],
  "job_category": string or null
}

Rules:
- Do not invent facts that are not in the JD.
- Do not treat preferred skills as required skills.
- Keep technical keywords concise and normalized.
- If information is missing, use null or an empty list.
- Preserve the original JD language where helpful.
- Return JSON only. No Markdown.
"""


def analyze_jd(
    jd_text: str,
    *,
    use_llm: bool = False,
    service: LLMService | None = None,
) -> JobAnalysis:
    """Analyze a JD with LLM when enabled, otherwise fall back to mock rules."""
    normalized_jd = jd_text.strip()
    if not normalized_jd:
        raise ValueError("jd_text cannot be empty")

    if not use_llm:
        return _mock_jd_analysis(normalized_jd)

    try:
        return analyze_jd_with_llm(normalized_jd, service=service)
    except (LLMServiceError, ValidationError, ValueError, TypeError):
        return _mock_jd_analysis(normalized_jd)


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
    ]:
        normalized.setdefault(field, [])
    return JobAnalysis.model_validate(normalized)


def _mock_jd_analysis(jd_text: str) -> JobAnalysis:
    from app.services.mock_pipeline import mock_jd_analysis

    return mock_jd_analysis(jd_text)
