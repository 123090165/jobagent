from __future__ import annotations

import json

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.search_mission import (
    SearchMissionInput,
    SearchMissionInterpretation,
)
from app.services.llm_provider import JSONChatLLM


def interpret_search_mission(
    payload: SearchMissionInput,
    profile: ConfirmedProfile,
    *,
    llm_service: JSONChatLLM | None = None,
) -> tuple[SearchMissionInterpretation, str, str | None]:
    fallback = _deterministic_interpretation(payload, profile)
    if llm_service is None:
        return fallback, "deterministic", None
    try:
        response = llm_service.chat_completion_json(
            system_prompt=(
                "You interpret a job seeker's current search mission. Return JSON only. "
                "Separate hard constraints from preferences, do not invent intent or resume "
                "evidence, identify conflicts, state assumptions, and ask at most three "
                "high-impact clarification questions. Treat clarification_answers as user intent, "
                "apply them when resolving ambiguity, and never repeat an answered question. "
                "Use exactly these keys: target_roles, "
                "adjacent_roles, excluded_roles, preferred_industries, locations, "
                "work_arrangements, employment_types, must_have, nice_to_have, "
                "hard_constraints, soft_preferences, ranking_priorities, exploration_level, "
                "conflicts, assumptions, clarification_questions. All fields except "
                "exploration_level are string arrays."
            ),
            user_prompt=json.dumps(
                {
                    "confirmed_profile": profile.model_dump(mode="json"),
                    "mission_input": payload.model_dump(mode="json"),
                    "deterministic_baseline": fallback.model_dump(mode="json"),
                }
            ),
        )
        interpreted = SearchMissionInterpretation.model_validate(response)
        interpreted = interpreted.model_copy(
            update={
                "clarification_questions": interpreted.clarification_questions[:3],
            }
        )
        if not interpreted.target_roles:
            interpreted = interpreted.model_copy(update={"target_roles": fallback.target_roles})
        return interpreted, "llm", None
    except Exception as exc:
        return fallback, "fallback", str(exc) or type(exc).__name__


def _deterministic_interpretation(
    payload: SearchMissionInput,
    profile: ConfirmedProfile,
) -> SearchMissionInterpretation:
    answered_questions = {
        item.question.casefold(): item.answer for item in payload.clarification_answers
    }
    target_role_question = "What role should this search prioritize?"
    target_role_answer = answered_questions.get(target_role_question.casefold())
    target_roles = payload.target_roles or (
        _answer_items(target_role_answer) if target_role_answer else profile.target_roles
    )
    locations = payload.locations or profile.preferred_locations
    work_arrangements = payload.work_arrangements or profile.work_arrangements
    profile_text = " ".join(
        profile.target_roles
        + profile.target_directions
        + profile.core_skills
        + profile.supporting_skills
        + [profile.summary]
    ).casefold()
    conflicts: list[str] = []
    questions: list[str] = []
    if set(item.casefold() for item in target_roles) & set(
        item.casefold() for item in payload.excluded_roles
    ):
        conflicts.append("A target role is also listed as an excluded role.")
        _append_unanswered_question(
            questions,
            answered_questions,
            "Which role should take priority where target and exclusion lists overlap?",
        )
    unsupported_roles = [role for role in target_roles if role.casefold() not in profile_text]
    if unsupported_roles:
        conflicts.append(
            "The resume profile has limited explicit evidence for: " + ", ".join(unsupported_roles)
        )
    unsupported_must_have = [item for item in payload.must_have if item.casefold() not in profile_text]
    if unsupported_must_have:
        conflicts.append(
            "Must-have preferences are not evidenced in the resume: "
            + ", ".join(unsupported_must_have)
        )
        _append_unanswered_question(
            questions,
            answered_questions,
            "Are the unevidenced must-have items job requirements, or skills you already have but the resume omits?",
        )
    assumptions: list[str] = []
    if not locations:
        assumptions.append("Location is flexible because no location preference was provided.")
    if not payload.employment_types:
        assumptions.append("Employment type is flexible.")
    if payload.exploration_level == "exploratory":
        assumptions.append("Adjacent role titles may be included when skills transfer well.")
    assumptions.extend(
        f"User clarification: {item.answer}" for item in payload.clarification_answers
    )
    if not target_roles and target_role_question.casefold() not in answered_questions:
        questions.insert(0, target_role_question)
    return SearchMissionInterpretation(
        target_roles=target_roles,
        adjacent_roles=profile.target_directions if payload.exploration_level != "focused" else [],
        excluded_roles=payload.excluded_roles,
        preferred_industries=payload.preferred_industries,
        locations=locations,
        work_arrangements=work_arrangements,
        employment_types=payload.employment_types,
        must_have=payload.must_have,
        nice_to_have=payload.nice_to_have,
        hard_constraints=payload.must_have,
        soft_preferences=payload.nice_to_have + payload.preferred_industries,
        ranking_priorities=payload.ranking_priorities,
        exploration_level=payload.exploration_level,
        conflicts=conflicts,
        assumptions=assumptions,
        clarification_questions=questions[:3],
    )


def _append_unanswered_question(
    questions: list[str],
    answered_questions: dict[str, str],
    question: str,
) -> None:
    if question.casefold() not in answered_questions:
        questions.append(question)


def _answer_items(answer: str) -> list[str]:
    return [item.strip() for item in answer.replace("\n", ",").split(",") if item.strip()]
