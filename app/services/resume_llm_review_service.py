from __future__ import annotations

import json
from typing import Literal

from pydantic import ValidationError

from app.schemas.resume import ResumeProfile
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError

ResumeReviewMode = Literal["llm", "fallback"]


def build_llm_assisted_resume_review(
    resume_text: str,
    deterministic_profile: ResumeProfile,
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[ResumeProfile, list[str], ResumeReviewMode]:
    if llm_service is None:
        return (
            deterministic_profile,
            ["LLM resume analysis fallback triggered: llm_service_unavailable"],
            "fallback",
        )

    try:
        payload = llm_service.chat_completion_json(
            system_prompt=_system_prompt(),
            user_prompt=_user_prompt(resume_text, deterministic_profile),
        )
        profile_payload = payload.get("resume_profile", payload)
        improved_profile = ResumeProfile.model_validate(profile_payload)
    except (LLMServiceError, ValidationError, ValueError, TypeError) as exc:
        return (
            deterministic_profile,
            [f"LLM resume analysis fallback triggered: {type(exc).__name__}"],
            "fallback",
        )

    return improved_profile, _clean_warnings(payload.get("quality_warnings", [])), "llm"


def _system_prompt() -> str:
    return (
        "You are a careful resume analysis assistant. Correct and enrich the deterministic "
        "parser output only when the raw resume text supports it. Do not invent schools, "
        "degrees, employers, internships, projects, outcomes, certificates, or skills. "
        "If evidence is uncertain, preserve uncertainty in missing_info or quality_warnings. "
        "Return only JSON."
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
        "Deterministic parser output JSON:\n"
        f"{json.dumps(deterministic_profile.model_dump(mode='json'), ensure_ascii=False)}\n\n"
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
