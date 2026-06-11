from __future__ import annotations

import json

from app.agents.schemas import GeneratedGroundedQuestionDraft
from app.prompts.loader import load_prompt
from app.services.llm_service import LLMService
from app.services.project_challenge_planner import ChallengeRequirement


PROJECT_QUESTION_GENERATOR_PROMPT_VERSION = "project_question_generator_v1"


def generate_grounded_question_with_llm(
    *,
    llm_service: LLMService,
    requirement: ChallengeRequirement,
    job_title: str | None,
    job_category: str | None,
    prompt_version: str = PROJECT_QUESTION_GENERATOR_PROMPT_VERSION,
) -> GeneratedGroundedQuestionDraft:
    """Generate and validate one grounded project interview question."""
    if prompt_version != PROJECT_QUESTION_GENERATOR_PROMPT_VERSION:
        raise ValueError(f"Unsupported project question prompt version: {prompt_version}")

    system_prompt = load_prompt("project_challenge/question_generator/system.md")
    user_template = load_prompt("project_challenge/question_generator/user_template.md")
    user_prompt = user_template.format(
        requirement=requirement.requirement,
        match_level=requirement.match_level,
        related_resume_evidence=json.dumps(requirement.related_resume_evidence, ensure_ascii=False),
        job_title=job_title or "Unknown",
        job_category=job_category or "Unknown",
    )
    payload = llm_service.chat_completion_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    return GeneratedGroundedQuestionDraft.model_validate(payload)
