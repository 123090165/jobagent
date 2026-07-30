"""请求 LLM 审阅简历画像，并把输出限制在可验证的修改建议内。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from app.schemas.resume import ResumeProfile
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError

ResumeReviewMode = Literal["llm_guided", "fallback"]


@dataclass(frozen=True)
class ResumeReviewBuildResult:
    parsed_profile: ResumeProfile
    analysis_warnings: list[str]
    analysis_mode: ResumeReviewMode


def build_llm_assisted_resume_review(
    resume_text: str,
    deterministic_profile: ResumeProfile,
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[ResumeProfile, list[str], ResumeReviewMode]:
    result = build_guided_llm_resume_review(
        raw_resume_text=resume_text,
        deterministic_profile=deterministic_profile,
        llm_service=llm_service,
    )
    return result.parsed_profile, result.analysis_warnings, result.analysis_mode


def build_guided_llm_resume_review(
    raw_resume_text: str,
    deterministic_profile: ResumeProfile,
    llm_service: JSONChatLLM | None,
) -> ResumeReviewBuildResult:
    if llm_service is None:
        return ResumeReviewBuildResult(
            parsed_profile=deterministic_profile,
            analysis_warnings=[
                "LLM resume analysis fallback triggered: llm_service_unavailable"
            ],
            analysis_mode="fallback",
        )

    try:
        payload = llm_service.chat_completion_json(
            system_prompt=_system_prompt(),
            user_prompt=_user_prompt(raw_resume_text, deterministic_profile),
        )
        if not isinstance(payload, dict):
            raise ValueError("LLM response must be a JSON object.")
        profile_payload = payload.get("resume_profile", payload)
        improved_profile = ResumeProfile.model_validate(profile_payload)
    except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
        reason = _sanitize_fallback_reason(str(exc))
        return ResumeReviewBuildResult(
            parsed_profile=deterministic_profile,
            analysis_warnings=[
                f"LLM resume analysis fallback triggered: {type(exc).__name__}: {reason}"
            ],
            analysis_mode="fallback",
        )

    return ResumeReviewBuildResult(
        parsed_profile=improved_profile,
        analysis_warnings=_clean_warnings(payload.get("quality_warnings", [])),
        analysis_mode="llm_guided",
    )


def _system_prompt() -> str:
    return (
        "You are a careful guided resume extraction assistant. Return JSON only. "
        "The raw resume text is authoritative and is the only source of truth. "
        "The deterministic profile is only a non-authoritative candidate hint and may be "
        "incomplete or wrong. Verify, reject, merge, correct, or supplement candidates "
        "based only on the raw resume. Do not invent schools, companies, projects, "
        "skills, certificates, dates, metrics, target roles, locations, or outcomes. "
        "If uncertain, use empty fields and quality_warnings or missing_info rather than "
        "guessing. Preserve explicit target roles and preferred locations when clearly "
        "stated in the raw text."
    )


def _user_prompt(resume_text: str, deterministic_profile: ResumeProfile) -> str:
    schema = {
        "resume_profile": {
            "raw_text": "string",
            "name": "string or null",
            "target_roles": ["string"],
            "education": [{"school": "string or null", "degree": "string or null", "major": "string or null", "raw_text": "string"}],
            "skills": ["string"],
            "projects": [{"name": "string or null", "description": "string", "technologies": ["string"], "highlights": ["string"], "raw_text": "string"}],
            "work_experiences": [{"company": "string or null", "role": "string or null", "description": "string", "technologies": ["string"], "raw_text": "string"}],
            "certificates": ["string"],
            "highlights": ["string"],
            "missing_info": ["string"],
        },
        "quality_warnings": ["string"],
    }
    return (
        "Raw resume text:\n"
        f"{resume_text}\n\n"
        "Non-authoritative deterministic candidate profile JSON:\n"
        f"{json.dumps(deterministic_profile.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        "Instructions:\n"
        "- Produce the final production ResumeProfile only from raw resume evidence.\n"
        "- Correct or remove deterministic candidates that the raw text does not support.\n"
        "- Use [] for absent list fields and null for absent optional scalar fields.\n"
        "- Put uncertainty or absent evidence in resume_profile.missing_info and quality_warnings.\n\n"
        "Required output schema JSON:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )


def _clean_warnings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _sanitize_fallback_reason(reason: str) -> str:
    text = reason.strip() or "No error details provided."
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [masked]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(?i)(DEEPSEEK_API_KEY|JOBAGENT_LLM_API_KEY|api[_-]?key|token|secret)\s*[:=]\s*['\"]?[^'\"\s,;]+",
        r"\1=[masked]",
        text,
    )
    text = re.sub(
        r"\b(sk-[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{32,})\b",
        "[masked]",
        text,
    )
    return text
