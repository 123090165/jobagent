from __future__ import annotations

import json
import re
from uuid import NAMESPACE_URL, uuid5

from app.prompts.loader import load_prompt
from app.schemas.interview_preparation import (
    PreparationAnswer,
    PreparationAnswerOption,
    PreparationGenerationStage,
    PreparationQuestion,
    PreparationRecommendation,
    PreparationSkillGap,
)
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob, SavedJobAnalysis
from app.services.llm_provider import JSONChatLLM
from app.services.llm_service import LLMServiceError


QUESTIONS_PROMPT_VERSION = "interview_preparation_questions_v3"
RECOMMENDATIONS_PROMPT_VERSION = "interview_preparation_recommendations_v2"
ANSWER_CLASSIFICATION_PROMPT_VERSION = "interview_preparation_answer_classification_v1"
QUESTIONS_SYSTEM_PROMPT = load_prompt("interview_preparation/questions_system.md")
RECOMMENDATIONS_SYSTEM_PROMPT = load_prompt(
    "interview_preparation/recommendations_system.md"
)
ANSWER_CLASSIFICATION_SYSTEM_PROMPT = load_prompt(
    "interview_preparation/answer_classification_system.md"
)

KNOWN_SKILLS = (
    "Microsoft Office", "Excel", "PowerPoint", "Word", "Linux", "SQL",
    "Python", "Java", "C++", "Git", "Docker", "Kubernetes", "FastAPI",
    "communication", "project management", "data analysis", "machine learning",
)

def generate_preparation_questions(
    job: SavedJob,
    profile: ResumeProfile | None,
    analysis: SavedJobAnalysis | None,
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[
    list[PreparationSkillGap],
    list[PreparationQuestion],
    PreparationGenerationStage,
]:
    fallback_gaps = _deterministic_gaps(job, profile, analysis)
    fallback_questions = _deterministic_questions(fallback_gaps)
    if llm_service is None:
        return fallback_gaps, fallback_questions, PreparationGenerationStage(
            mode="deterministic",
            prompt_version=QUESTIONS_PROMPT_VERSION,
            attempts=0,
        )

    user_prompt = json.dumps(_question_generation_memory(
        job, profile, analysis, fallback_gaps, fallback_questions
    ), ensure_ascii=False)
    errors: list[str] = []
    for attempt in range(1, 3):
        try:
            response = llm_service.chat_completion_json(
                system_prompt=_prompt_for_attempt(
                    QUESTIONS_SYSTEM_PROMPT,
                    attempt=attempt,
                    expected_shape='{ "skill_gaps": [...], "questions": [...] }',
                ),
                user_prompt=user_prompt,
            )
            raw_gaps = response.get("skill_gaps")
            raw_questions = response.get("questions")
            if not isinstance(raw_gaps, list) or not isinstance(raw_questions, list):
                raise TypeError("skill_gaps and questions must both be JSON arrays")
            gaps = [PreparationSkillGap.model_validate(item) for item in raw_gaps][:8]
            if not gaps:
                raise ValueError("No skill gaps returned")
            questions = _questions_with_ids(raw_questions, require_model_options=True)[:5]
            questions = questions or _deterministic_questions(gaps) or fallback_questions
            return gaps, questions, PreparationGenerationStage(
                mode="llm",
                prompt_version=QUESTIONS_PROMPT_VERSION,
                attempts=attempt,
                attempt_errors=errors,
            )
        except Exception as exc:
            errors.append(_error_summary(exc))
            if attempt == 1 and _is_retryable_generation_error(exc):
                continue
            break
    return fallback_gaps, fallback_questions, PreparationGenerationStage(
        mode="fallback",
        prompt_version=QUESTIONS_PROMPT_VERSION,
        attempts=len(errors),
        fallback_reason=errors[-1],
        attempt_errors=errors,
    )


def generate_recommendations(
    gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
    answers: list[PreparationAnswer],
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[list[PreparationRecommendation], PreparationGenerationStage]:
    fallback = _deterministic_recommendations(gaps, questions, answers)
    if llm_service is None:
        return fallback, PreparationGenerationStage(
            mode="deterministic",
            prompt_version=RECOMMENDATIONS_PROMPT_VERSION,
            attempts=0,
        )

    user_prompt = json.dumps(
        {
            "skill_gaps": [item.model_dump() for item in gaps],
            "questions": [item.model_dump() for item in questions],
            "user_answers": [item.model_dump() for item in answers],
            "deterministic_baseline": [item.model_dump() for item in fallback],
        },
        ensure_ascii=False,
    )
    errors: list[str] = []
    for attempt in range(1, 3):
        try:
            response = llm_service.chat_completion_json(
                system_prompt=_prompt_for_attempt(
                    RECOMMENDATIONS_SYSTEM_PROMPT,
                    attempt=attempt,
                    expected_shape='{ "recommendations": [...] }',
                ),
                user_prompt=user_prompt,
                expected_root_key="recommendations",
            )
            raw_items = response.get("recommendations")
            if not isinstance(raw_items, list):
                raise TypeError("recommendations must be a JSON array")
            items = [
                PreparationRecommendation.model_validate(item) for item in raw_items
            ][:6]
            if not items:
                raise ValueError("No recommendations returned")
            return items, PreparationGenerationStage(
                mode="llm",
                prompt_version=RECOMMENDATIONS_PROMPT_VERSION,
                attempts=attempt,
                attempt_errors=errors,
            )
        except Exception as exc:
            errors.append(_error_summary(exc))
            if attempt == 1 and _is_retryable_generation_error(exc):
                continue
            break
    return fallback, PreparationGenerationStage(
        mode="fallback",
        prompt_version=RECOMMENDATIONS_PROMPT_VERSION,
        attempts=len(errors),
        fallback_reason=errors[-1],
        attempt_errors=errors,
    )


def resolve_preparation_answers(
    questions: list[PreparationQuestion],
    answers: list[PreparationAnswer],
    *,
    llm_service: JSONChatLLM | None,
) -> list[PreparationAnswer]:
    """Resolve UI answers into the small, backend-owned transition vocabulary."""
    question_by_id = {item.question_id: item for item in questions}
    resolved: list[PreparationAnswer] = []
    free_text_answers: list[PreparationAnswer] = []
    for answer in answers:
        question = question_by_id.get(answer.question_id)
        if question is None:
            continue
        if answer.response_mode == "free_text":
            free_text_answers.append(answer)
            continue
        option = _selected_option(question, answer)
        if option is None:
            raise ValueError(f"Unknown option for question {answer.question_id}")
        resolved.append(_answer_from_option(answer, option, source="option"))

    if not free_text_answers:
        return _restore_answer_order(answers, resolved)

    classified: dict[str, str] = {}
    if llm_service is not None:
        payload = {
            "routing_policy": {
                "prefer_closest_option": True,
                "do_not_infer_unstated_experience": True,
                "uncertain_when_ambiguous": True,
            },
            "dialogue_memory": [
                {
                    "question": question_by_id[item.question_id].model_dump(mode="json"),
                    "free_text": item.free_text or item.answer,
                }
                for item in free_text_answers
            ],
        }
        try:
            response = llm_service.chat_completion_json(
                system_prompt=ANSWER_CLASSIFICATION_SYSTEM_PROMPT,
                user_prompt=json.dumps(payload, ensure_ascii=False),
                expected_root_key="classifications",
            )
            for item in response.get("classifications", []):
                if isinstance(item, dict):
                    classified[str(item.get("question_id") or "")] = str(
                        item.get("option_id") or ""
                    )
        except Exception:
            classified = {}

    for answer in free_text_answers:
        question = question_by_id[answer.question_id]
        option = next(
            (item for item in question.options if item.option_id == classified.get(answer.question_id)),
            None,
        )
        source = "llm_classified"
        if option is None:
            option = next((item for item in question.options if item.value == "uncertain"), None)
            source = "fallback_uncertain"
        if option is None:
            option = PreparationAnswerOption(
                option_id="fallback_uncertain",
                value="uncertain",
                label="Needs clarification",
                description="The response could not be mapped safely to the available choices.",
                evidence_transition="unknown",
                route="clarify",
                detail_policy="optional",
            )
        resolved.append(_answer_from_option(answer, option, source=source))
    return _restore_answer_order(answers, resolved)


def _selected_option(
    question: PreparationQuestion, answer: PreparationAnswer
) -> PreparationAnswerOption | None:
    if answer.selected_option_id:
        selected = next(
            (item for item in question.options if item.option_id == answer.selected_option_id),
            None,
        )
        if selected is not None:
            return selected
    if answer.experience_level:
        return next(
            (item for item in question.options if item.value == answer.experience_level),
            None,
        )
    return None


def _answer_from_option(
    answer: PreparationAnswer,
    option: PreparationAnswerOption,
    *,
    source: str,
) -> PreparationAnswer:
    return answer.model_copy(update={
        "selected_option_id": option.option_id,
        "experience_level": option.value,
        "evidence_transition": option.evidence_transition,
        "route": option.route,
        "resolution_source": source,
    })


def _restore_answer_order(
    original: list[PreparationAnswer], resolved: list[PreparationAnswer]
) -> list[PreparationAnswer]:
    by_id = {item.question_id: item for item in resolved}
    return [by_id[item.question_id] for item in original if item.question_id in by_id]


def _prompt_for_attempt(base_prompt: str, *, attempt: int, expected_shape: str) -> str:
    if attempt == 1:
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "FORMAT CORRECTION: The previous response was rejected by the local JSON/schema "
        "validator. Re-evaluate the supplied context, but correct only the output contract. "
        f"Return exactly one JSON object shaped like {expected_shape}. Do not return a "
        "top-level array, prose, markdown, or an empty result."
    )


def _is_retryable_generation_error(exc: Exception) -> bool:
    if isinstance(exc, LLMServiceError):
        message = str(exc).casefold()
        return any(
            marker in message
            for marker in ("json", "message content", "does not contain message")
        )
    return isinstance(exc, (KeyError, TypeError, ValueError))


def _error_summary(exc: Exception) -> str:
    message = (str(exc) or type(exc).__name__).strip().replace("\n", " ")
    return f"{type(exc).__name__}: {message}"[:500]


def build_external_prompt(
    job: SavedJob,
    profile: ResumeProfile | None,
    gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
) -> str:
    payload = {
        "job": {"title": job.title, "company": job.company, "jd": job.raw_jd_text},
        "profile": profile.model_dump(mode="json") if profile else None,
        "skill_gaps": [item.model_dump() for item in gaps],
        "questions": [item.model_dump() for item in questions],
    }
    return (
        "JOBAGENT EVIDENCE INTERVIEW\n\n"
        "Act as an evidence interviewer. Present each question's supplied options one at a time. "
        "If an option is selected, obey its detail_policy and use only its focused follow_up_prompt. "
        "Use free text only when every option materially distorts the user's situation. Do not invent "
        "experience and allow the user to say they have none. At the end, return JSON with an answers "
        "array containing question_id, response_mode, selected_option_id or free_text, and optional "
        "detail. Treat all answers as user-reported, not verified resume evidence.\n\nCONTEXT JSON:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _deterministic_gaps(
    job: SavedJob, profile: ResumeProfile | None, analysis: SavedJobAnalysis | None
) -> list[PreparationSkillGap]:
    jd_text = job.raw_jd_text
    profile_text = " ".join(
        (profile.core_skills + profile.supporting_skills + profile.strengths + [profile.summary])
        if profile else []
    )
    skills = [skill for skill in KNOWN_SKILLS if re.search(rf"\b{re.escape(skill)}\b", jd_text, re.I)]
    for item in (analysis.critical_gaps if analysis else []):
        for skill in KNOWN_SKILLS:
            if skill.casefold() in item.casefold() and skill not in skills:
                skills.append(skill)
    gaps: list[PreparationSkillGap] = []
    for index, skill in enumerate(skills[:8]):
        supported = re.search(rf"\b{re.escape(skill)}\b", profile_text, re.I) is not None
        gaps.append(PreparationSkillGap(
            skill=skill,
            importance="high" if index < 3 else "medium",
            evidence_status="partial" if supported else "unknown",
            skill_type="experience" if skill.casefold() in {"communication", "project management"} else "knowledge",
            jd_evidence=_sentence_containing(jd_text, skill),
            profile_evidence=[skill] if supported else [],
            rationale=(
                "The profile mentions this skill but lacks a concrete example."
                if supported else "The JD mentions this skill and the profile has no explicit evidence."
            ),
        ))
    if not gaps:
        gaps.append(PreparationSkillGap(
            skill="role-specific execution",
            importance="high", evidence_status="unknown", skill_type="experience",
            jd_evidence=jd_text[:300], profile_evidence=[],
            rationale="The JD should be validated against a concrete example from the user.",
        ))
    return gaps


def _deterministic_questions(gaps: list[PreparationSkillGap]) -> list[PreparationQuestion]:
    items = []
    for gap in [item for item in gaps if item.evidence_status in {"partial", "unknown", "missing"}][:5]:
        prompt = f"Which description is closest to your current experience with {gap.skill}?"
        question_id = str(uuid5(NAMESPACE_URL, f"{gap.skill}:{prompt}"))
        items.append(PreparationQuestion(
            question_id=question_id, skill=gap.skill, prompt=prompt,
            why_asked=f"The JD treats {gap.skill} as important, but current evidence is {gap.evidence_status}.",
            options=_fallback_options(gap),
        ))
    return items


def _questions_with_ids(
    items: list[object], *, require_model_options: bool = False
) -> list[PreparationQuestion]:
    questions = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        prompt = str(raw.get("prompt") or "").strip()
        skill = str(raw.get("skill") or "").strip()
        if not prompt or not skill:
            continue
        raw_options = raw.get("options")
        if require_model_options and (
            not isinstance(raw_options, list) or not 2 <= len(raw_options) <= 6
        ):
            raise ValueError(f"Question for {skill} must contain 2-6 tailored options")
        options = []
        for index, item in enumerate(raw_options or []):
            if not isinstance(item, dict):
                raise TypeError(f"Question option {index} for {skill} must be an object")
            option = {**item}
            option.setdefault(
                "option_id",
                str(uuid5(NAMESPACE_URL, f"{skill}:{prompt}:{index}:{item.get('value', '')}")),
            )
            options.append(PreparationAnswerOption.model_validate(option))
        questions.append(PreparationQuestion(
            question_id=str(uuid5(NAMESPACE_URL, f"{skill}:{prompt}")),
            skill=skill, prompt=prompt,
            why_asked=str(raw.get("why_asked") or "Clarifies an important evidence gap."),
            options=options,
            free_text_allowed=bool(raw.get("free_text_allowed", True)),
            free_text_prompt=str(raw.get("free_text_prompt") or (
                "If none of these options describes your situation accurately, explain what is different."
            )),
        ))
    return questions


def _fallback_options(gap: PreparationSkillGap) -> list[PreparationAnswerOption]:
    skill = gap.skill
    return [
        PreparationAnswerOption(
            option_id="delivered_result",
            value="work_experience",
            label=f"Delivered {skill} in professional work",
            description="I owned a relevant task or deliverable in a real work setting.",
            evidence_transition="supported",
            route="ask_evidence",
            detail_policy="required",
            follow_up_prompt="What did you personally own, and how was the result evaluated?",
        ),
        PreparationAnswerOption(
            option_id="substantial_project",
            value="project_experience",
            label=f"Applied {skill} in a substantial project",
            description="I implemented or evaluated it in an academic, personal, or team project.",
            evidence_transition="supported",
            route="ask_evidence",
            detail_policy="required",
            follow_up_prompt="What did you implement personally, and what evidence shows how it worked?",
        ),
        PreparationAnswerOption(
            option_id="guided_practice",
            value="practice_only",
            label=f"Practised {skill} in guided work",
            description="I completed coursework, tutorials, or small exercises but not a substantial project.",
            evidence_transition="partial",
            route="learning",
            detail_policy="optional",
            follow_up_prompt="Which parts have you practised, and which still need hands-on work?",
        ),
        PreparationAnswerOption(
            option_id="concept_only",
            value="conceptual_only",
            label=f"Understand {skill} only conceptually",
            description="I know the main ideas but have not applied them hands-on.",
            evidence_transition="partial",
            route="learning",
            detail_policy="not_needed",
        ),
        PreparationAnswerOption(
            option_id="no_current_experience",
            value="no_experience",
            label=f"No current experience with {skill}",
            description="I have not learned or used this capability yet.",
            evidence_transition="missing",
            route="capability_gap",
            detail_policy="not_needed",
        ),
        PreparationAnswerOption(
            option_id="needs_context",
            value="uncertain",
            label="I need a more specific distinction",
            description="My situation overlaps multiple choices or the question is too broad.",
            evidence_transition="unknown",
            route="clarify",
            detail_policy="optional",
            follow_up_prompt="What part of the choices does not fit your actual situation?",
        ),
    ]


def _question_generation_memory(
    job: SavedJob,
    profile: ResumeProfile | None,
    analysis: SavedJobAnalysis | None,
    fallback_gaps: list[PreparationSkillGap],
    fallback_questions: list[PreparationQuestion],
) -> dict[str, object]:
    profile_dump = profile.model_dump(mode="json") if profile else None
    return {
        "job_requirement_memory": {
            "saved_job_id": job.saved_job_id,
            "title": job.title,
            "company": job.company,
            "raw_jd_text": job.raw_jd_text,
            "structured_jd": job.structured_jd,
        },
        "profile_evidence_memory": {
            "resume_profile_id": profile.resume_profile_id if profile else None,
            "immutable_profile": profile_dump,
            "rule": "Absence of profile evidence means unknown, never missing or negative experience.",
        },
        "analysis_memory": analysis.model_dump(mode="json") if analysis else None,
        "gap_state_memory": [item.model_dump(mode="json") for item in fallback_gaps],
        "routing_policy": {
            "model_proposes_semantics": True,
            "backend_validates_transitions": True,
            "option_count": "2-6 per question",
            "free_text_is_escape_hatch": True,
            "ask_evidence_only_when_an_example_can_change_the_state": True,
            "knowledge_gap_routes_to_learning": True,
            "explicit_absence_routes_to_capability_gap": True,
        },
        "deterministic_baseline": {
            "skill_gaps": [item.model_dump(mode="json") for item in fallback_gaps],
            "questions": [item.model_dump(mode="json") for item in fallback_questions],
        },
    }


def _deterministic_recommendations(
    gaps: list[PreparationSkillGap], questions: list[PreparationQuestion], answers: list[PreparationAnswer]
) -> list[PreparationRecommendation]:
    answer_by_id = {item.question_id: item for item in answers}
    question_by_skill = {item.skill: item for item in questions}
    result = []
    for gap in gaps[:6]:
        question = question_by_skill.get(gap.skill)
        answer = answer_by_id.get(question.question_id) if question else None
        detail = (answer.detail or answer.free_text or answer.answer or "") if answer else ""
        level = answer.experience_level if answer else None
        if level in {"work_experience", "project_experience"}:
            action = f"Turn the user-reported {gap.skill} example into a concise context-action-result story."
            basis = [detail[:300]] if detail else [f"User selected {level.replace('_', ' ')}."]
            action_type = "interview_story" if detail else "experience_inventory"
        elif level in {"practice_only", "conceptual_only"}:
            action = f"Build hands-on confidence in {gap.skill} with a focused exercise before preparing an interview explanation."
            basis = [gap.jd_evidence]
            action_type = "learning"
        elif level == "no_experience":
            action = f"Treat {gap.skill} as a current capability gap and avoid presenting it as prior experience."
            basis = [gap.jd_evidence]
            action_type = "capability_gap"
        elif detail:
            action = f"Clarify the user-reported {gap.skill} example before using it in interview preparation."
            basis = [detail[:300]]
            action_type = "experience_inventory"
        elif gap.skill_type == "knowledge":
            action = f"Review {gap.skill}, then prepare one truthful example or state the current limitation."
            basis = [gap.jd_evidence]
            action_type = "learning"
        else:
            action = f"Prepare a concrete {gap.skill} example; do not claim experience that is not available."
            basis = [gap.jd_evidence]
            action_type = "experience_inventory"
        result.append(PreparationRecommendation(
            title=gap.skill, skill=gap.skill, action=action,
            action_type=action_type, evidence_basis=basis,
        ))
    return result


def _sentence_containing(text: str, term: str) -> str:
    sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    return next((item.strip() for item in sentences if term.casefold() in item.casefold()), text[:300])
