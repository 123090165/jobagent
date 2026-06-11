from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.job import JobAnalysis

JDAnalysisQualityLabel = Literal["high", "medium", "low"]

SPARSE_REQUIRED_SKILLS_WARNING = "required_skills appear too sparse for the JD length"
FEWER_THAN_BASELINE_WARNING = "LLM required_skills are much fewer than deterministic baseline"
RESPONSIBILITIES_METADATA_WARNING = "responsibilities may contain metadata instead of job duties"
VERBOSE_SKILL_WARNING = "skill entries may be too verbose"
EMPTY_KEYWORDS_WARNING = "keywords appear empty"
VERBOSE_KEYWORDS_WARNING = "keyword entries may be too verbose"
UNGROUNDED_METADATA_WARNING = "metadata may not be grounded in JD text"


class JDAnalysisQualityReport(BaseModel):
    quality_label: JDAnalysisQualityLabel
    warnings: list[str] = Field(default_factory=list)
    fallback_recommended: bool = False
    checked_rules: list[str] = Field(default_factory=list)


def evaluate_jd_analysis_quality(
    *,
    jd_text: str,
    llm_analysis: JobAnalysis,
    baseline_analysis: JobAnalysis | None = None,
) -> JDAnalysisQualityReport:
    normalized_jd = jd_text.strip()
    warnings: list[str] = []
    checked_rules: list[str] = []

    checked_rules.append("required_skills_sparse_for_jd_length")
    if len(normalized_jd) >= 240 and len(llm_analysis.required_skills) < 2:
        warnings.append(SPARSE_REQUIRED_SKILLS_WARNING)

    checked_rules.append("required_skills_compared_to_baseline")
    if baseline_analysis is not None and len(llm_analysis.required_skills) < max(
        2,
        len(baseline_analysis.required_skills) * 0.6,
    ):
        warnings.append(FEWER_THAN_BASELINE_WARNING)

    checked_rules.append("responsibilities_metadata_pollution")
    if any(_looks_like_metadata_line(item) for item in llm_analysis.responsibilities):
        warnings.append(RESPONSIBILITIES_METADATA_WARNING)

    checked_rules.append("skill_entry_length")
    if any(len(skill) > 60 for skill in [*llm_analysis.required_skills, *llm_analysis.preferred_skills]):
        warnings.append(VERBOSE_SKILL_WARNING)

    checked_rules.append("keyword_presence_and_length")
    if not llm_analysis.keywords:
        warnings.append(EMPTY_KEYWORDS_WARNING)
    elif _mostly_verbose(llm_analysis.keywords, max_length=40):
        warnings.append(VERBOSE_KEYWORDS_WARNING)

    checked_rules.append("metadata_grounding")
    if _has_ungrounded_metadata(normalized_jd, llm_analysis):
        warnings.append(UNGROUNDED_METADATA_WARNING)

    critical_warnings = {
        SPARSE_REQUIRED_SKILLS_WARNING,
        FEWER_THAN_BASELINE_WARNING,
        EMPTY_KEYWORDS_WARNING,
    }
    fallback_recommended = any(warning in critical_warnings for warning in warnings)
    if fallback_recommended:
        quality_label: JDAnalysisQualityLabel = "low"
    elif warnings:
        quality_label = "medium"
    else:
        quality_label = "high"

    return JDAnalysisQualityReport(
        quality_label=quality_label,
        warnings=warnings,
        fallback_recommended=fallback_recommended,
        checked_rules=checked_rules,
    )


def _looks_like_metadata_line(value: str) -> bool:
    normalized = value.strip().lower()
    metadata_prefixes = (
        "role:",
        "title:",
        "job title:",
        "company:",
        "location:",
        "地点：",
        "公司：",
        "岗位：",
        "职位：",
    )
    return normalized.startswith(metadata_prefixes)


def _mostly_verbose(values: list[str], *, max_length: int) -> bool:
    verbose_count = sum(1 for value in values if len(value) > max_length)
    return verbose_count > len(values) / 2


def _has_ungrounded_metadata(jd_text: str, analysis: JobAnalysis) -> bool:
    normalized_jd = jd_text.lower()
    for value in [analysis.job_title, analysis.company, analysis.location]:
        if value and value.lower() not in normalized_jd:
            return True
    return False
