"""根据证据缺口生成准备问题、追问、建议和可供外部模型使用的提示文本。"""

from __future__ import annotations

import json
import re
from uuid import NAMESPACE_URL, uuid5

from app.prompts.loader import load_prompt
from app.schemas.interview_preparation import (
    CapabilityDimension,
    OptionStateEffect,
    PreparationAnswer,
    PreparationAnswerOption,
    PreparationGenerationStage,
    PreparationQuestion,
    PreparationRecommendation,
    PreparationSkillGap,
    QuestionDecisionObjective,
)
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob, SavedJobAnalysis
from app.services.llm_provider import JSONChatLLM
from app.services.llm_observability import llm_observation_context
from app.services.llm_service import LLMServiceError


QUESTIONS_PROMPT_VERSION = "interview_preparation_questions_v8"
NEXT_QUESTION_PROMPT_VERSION = "interview_preparation_next_question_v3"
RECOMMENDATIONS_PROMPT_VERSION = "interview_preparation_recommendations_v4"
ANSWER_CLASSIFICATION_PROMPT_VERSION = "interview_preparation_answer_classification_v1"
QUESTIONS_SYSTEM_PROMPT = load_prompt("interview_preparation/questions_system.md")
NEXT_QUESTION_SYSTEM_PROMPT = load_prompt("interview_preparation/next_question_system.md")
RECOMMENDATIONS_SYSTEM_PROMPT = load_prompt(
    "interview_preparation/recommendations_system.md"
)
ANSWER_CLASSIFICATION_SYSTEM_PROMPT = load_prompt(
    "interview_preparation/answer_classification_system.md"
)

KNOWN_SKILLS = (
    "Microsoft Office", "Excel", "PowerPoint", "Word", "Linux", "SQL",
    "Python", "Java", "C++", "Git", "Docker", "Kubernetes", "FastAPI",
    "PyTorch", "TensorFlow",
    "communication", "project management", "data analysis", "machine learning",
)

# Deterministic coverage anchors keep a valid-looking model response from
# silently collapsing a multi-skill JD into one or two generic gaps. The model
# still owns the job-specific wording, options, and routing semantics.
JD_REQUIREMENT_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "blood pressure estimation",
        "knowledge",
        (r"blood[ -]?pressure", r"血压", r"cuffless\s+BP"),
    ),
    (
        "multimodal physiological signal fusion",
        "knowledge",
        (r"multimodal.{0,40}fusion", r"多模态.{0,20}融合", r"多源.{0,20}融合"),
    ),
    ("PPG signal processing", "knowledge", (r"\bPPG\b", r"光电容积")),
    ("ECG signal processing", "knowledge", (r"\bECG\b", r"心电")),
    (
        "ACC motion signal analysis",
        "knowledge",
        (r"\bACC\b", r"acceleromet", r"加速度", r"运动信号"),
    ),
    (
        "motion-artifact handling",
        "knowledge",
        (r"motion artifact", r"运动伪影", r"运动干扰"),
    ),
    (
        "data annotation and quality assurance",
        "experience",
        (r"data annotation", r"数据标注", r"质量标准", r"quality assurance"),
    ),
    (
        "edge deployment and real-time optimization",
        "knowledge",
        (r"edge deploy", r"real[ -]?time", r"端侧", r"边缘部署", r"实时处理"),
    ),
    (
        "cross-team technical collaboration",
        "experience",
        (r"cross[ -]?functional", r"cross[ -]?team", r"跨团队", r"协同.{0,12}团队"),
    ),
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
        return fallback_gaps, fallback_questions[:2], PreparationGenerationStage(
            mode="deterministic",
            prompt_version=QUESTIONS_PROMPT_VERSION,
            attempts=0,
        )

    generation_memory = _question_generation_memory(
        job, profile, analysis, fallback_gaps
    )
    user_prompt = _json_prompt(generation_memory)
    errors: list[str] = []
    for attempt in range(1, 3):
        try:
            with llm_observation_context(
                "preparation.generate_questions",
                metadata={
                    "stage": "question_generation",
                    "attempt": attempt,
                    "prompt_version": QUESTIONS_PROMPT_VERSION,
                    "saved_job_id": job.saved_job_id,
                },
                context_parts=generation_memory,
            ):
                response = llm_service.chat_completion_json(
                    system_prompt=_prompt_for_attempt(
                        QUESTIONS_SYSTEM_PROMPT,
                        attempt=attempt,
                        expected_shape='{ "skill_gaps": [...], "questions": [...] }',
                        correction=errors[-1] if errors else None,
                    ),
                    user_prompt=user_prompt,
                )
            raw_gaps = response.get("skill_gaps")
            raw_questions = response.get("questions")
            if not isinstance(raw_gaps, list) or not isinstance(raw_questions, list):
                raise TypeError("skill_gaps and questions must both be JSON arrays")
            gaps = [PreparationSkillGap.model_validate(item) for item in raw_gaps][:8]
            gaps = [item if item.dimensions else item.model_copy(update={
                "dimensions": _default_capability_dimensions(item.skill)
            }) for item in gaps]
            if not gaps:
                raise ValueError("No skill gaps returned")
            questions = _questions_with_ids(raw_questions, require_model_options=True)[:2]
            questions = questions or _deterministic_questions(gaps) or fallback_questions
            _validate_question_coverage(fallback_gaps, gaps, questions)
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
    return fallback_gaps, fallback_questions[:2], PreparationGenerationStage(
        mode="fallback",
        prompt_version=QUESTIONS_PROMPT_VERSION,
        attempts=len(errors),
        fallback_reason=errors[-1],
        attempt_errors=errors,
    )


def generate_next_preparation_question(
    gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
    answers: list[PreparationAnswer],
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[PreparationQuestion | None, PreparationGenerationStage]:
    locked_dimensions = {
        item.decision_objective.dimension_id
        for item in questions if item.decision_objective is not None
    }
    remaining = []
    for gap in gaps:
        dimensions = [
            item for item in (gap.dimensions or _default_capability_dimensions(gap.skill))
            if item.state in {"unresolved", "partial", "unknown"}
            and item.dimension_id not in locked_dimensions
        ]
        if dimensions:
            remaining.append(gap.model_copy(update={"dimensions": dimensions}))
    fallback = (_deterministic_questions(remaining) or [None])[0]
    if not remaining or len(questions) >= 5:
        return None, PreparationGenerationStage(
            mode="deterministic", prompt_version=NEXT_QUESTION_PROMPT_VERSION, attempts=0
        )
    if llm_service is None:
        return fallback, PreparationGenerationStage(
            mode="deterministic", prompt_version=NEXT_QUESTION_PROMPT_VERSION, attempts=0
        )

    memory = _next_question_memory(gaps, remaining, questions, answers)
    errors: list[str] = []
    for attempt in range(1, 3):
        try:
            with llm_observation_context(
                "preparation.generate_next_question",
                metadata={
                    "stage": "next_question_generation",
                    "attempt": attempt,
                    "prompt_version": NEXT_QUESTION_PROMPT_VERSION,
                    "question_index": len(questions) + 1,
                    "locked_question_count": len(questions),
                    "committed_answer_count": len(
                        [item for item in answers if item.committed]
                    ),
                },
                context_parts=memory,
            ):
                response = llm_service.chat_completion_json(
                    system_prompt=_prompt_for_attempt(
                        NEXT_QUESTION_SYSTEM_PROMPT,
                        attempt=attempt,
                        expected_shape='{ "question": { ... } }',
                        correction=errors[-1] if errors else None,
                    ),
                    user_prompt=_json_prompt(memory),
                )
            raw = response.get("question")
            if not isinstance(raw, dict):
                raise TypeError("question must be a JSON object")
            generated = _questions_with_ids([raw], require_model_options=True)
            if not generated:
                raise ValueError("No usable next question returned")
            question = generated[0]
            if _normalized_skill(question.skill) not in {
                _normalized_skill(item.skill) for item in remaining
            }:
                raise ValueError("Next question must target a remaining skill gap")
            target_gap = next(
                item for item in remaining
                if _normalized_skill(item.skill) == _normalized_skill(question.skill)
            )
            remaining_dimensions = {item.dimension_id for item in target_gap.dimensions}
            if (
                question.decision_objective is None
                or question.decision_objective.dimension_id not in remaining_dimensions
            ):
                raise ValueError("Next question must target an unresolved capability dimension")
            _validate_question_not_generic(question, questions)
            return question, PreparationGenerationStage(
                mode="llm", prompt_version=NEXT_QUESTION_PROMPT_VERSION,
                attempts=attempt, attempt_errors=errors,
            )
        except Exception as exc:
            errors.append(_error_summary(exc))
            if attempt == 1 and _is_retryable_generation_error(exc):
                continue
            break
    return fallback, PreparationGenerationStage(
        mode="fallback", prompt_version=NEXT_QUESTION_PROMPT_VERSION,
        attempts=len(errors), fallback_reason=errors[-1], attempt_errors=errors,
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

    recommendation_memory = _recommendation_memory(
        gaps, questions, answers, fallback
    )
    user_prompt = _json_prompt(recommendation_memory)
    errors: list[str] = []
    for attempt in range(1, 3):
        try:
            with llm_observation_context(
                "preparation.generate_recommendations",
                metadata={
                    "stage": "recommendation_generation",
                    "attempt": attempt,
                    "prompt_version": RECOMMENDATIONS_PROMPT_VERSION,
                },
                context_parts=recommendation_memory,
            ):
                response = llm_service.chat_completion_json(
                    system_prompt=_prompt_for_attempt(
                        RECOMMENDATIONS_SYSTEM_PROMPT,
                        attempt=attempt,
                        expected_shape='{ "recommendations": [...] }',
                        correction=errors[-1] if errors else None,
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
    classify_free_text: bool = True,
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
            if answer.selected_option_id and answer.resolution_source in {
                "llm_classified", "fallback_uncertain"
            } and answer.follow_up_count == 0:
                option = _selected_option(question, answer)
                if option is not None:
                    resolved.append(_answer_from_option(
                        answer, option, source=answer.resolution_source
                    ))
                    continue
            if not classify_free_text:
                resolved.append(answer)
                continue
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
            with llm_observation_context(
                "preparation.classify_free_text",
                metadata={
                    "stage": "answer_classification",
                    "prompt_version": ANSWER_CLASSIFICATION_PROMPT_VERSION,
                    "answer_count": len(free_text_answers),
                },
                context_parts=payload,
            ):
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


def _prompt_for_attempt(
    base_prompt: str,
    *,
    attempt: int,
    expected_shape: str,
    correction: str | None = None,
) -> str:
    if attempt == 1:
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "FORMAT CORRECTION: The previous response was rejected by the local JSON/schema "
        "validator. Re-evaluate the supplied context and correct the specific contract or "
        "coverage issue reported below. Do not change grounded facts merely to pass validation. "
        f"Return exactly one JSON object shaped like {expected_shape}. Do not return a "
        "top-level array, prose, markdown, or an empty result. "
        f"Previous validator error: {correction or 'output contract rejected'}."
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
    jd_text = _job_requirement_text(job)
    profile_text = " ".join(
        (profile.core_skills + profile.supporting_skills + profile.strengths + [profile.summary])
        if profile else []
    )
    detected: list[tuple[str, str, str]] = []
    for skill, skill_type, patterns in JD_REQUIREMENT_PATTERNS:
        match = _first_pattern_match(patterns, jd_text)
        if match is not None:
            detected.append((skill, skill_type, match.group(0)))
    for skill in KNOWN_SKILLS:
        match = re.search(rf"\b{re.escape(skill)}\b", jd_text, re.I)
        if match is not None and not any(
            item[0].casefold() == skill.casefold() for item in detected
        ):
            skill_type = (
                "experience"
                if skill.casefold() in {"communication", "project management"}
                else "knowledge"
            )
            detected.append((skill, skill_type, match.group(0)))
    for item in (analysis.critical_gaps if analysis else []):
        for skill in KNOWN_SKILLS:
            if skill.casefold() in item.casefold() and not any(
                detected_skill.casefold() == skill.casefold()
                for detected_skill, _, _ in detected
            ):
                detected.append((skill, "knowledge", skill))
    gaps: list[PreparationSkillGap] = []
    for index, (skill, skill_type, matched_term) in enumerate(detected[:8]):
        patterns = next(
            (
                item_patterns
                for pattern_skill, _, item_patterns in JD_REQUIREMENT_PATTERNS
                if pattern_skill == skill
            ),
            (),
        )
        supported = _first_pattern_match(patterns, profile_text) is not None or (
            re.search(rf"\b{re.escape(skill)}\b", profile_text, re.I) is not None
        )
        gaps.append(PreparationSkillGap(
            skill=skill,
            importance="high" if index < 5 else "medium",
            evidence_status="partial" if supported else "unknown",
            skill_type=skill_type,
            jd_evidence=_sentence_containing(jd_text, matched_term),
            profile_evidence=[skill] if supported else [],
            rationale=(
                "The profile mentions this skill but lacks a concrete example."
                if supported else "The JD mentions this skill and the profile has no explicit evidence."
            ),
            dimensions=_default_capability_dimensions(skill),
        ))
    if not gaps:
        gaps.append(PreparationSkillGap(
            skill="role-specific execution",
            importance="high", evidence_status="unknown", skill_type="experience",
            jd_evidence=jd_text[:300], profile_evidence=[],
            rationale="The JD should be validated against a concrete example from the user.",
            dimensions=_default_capability_dimensions("role-specific execution"),
        ))
    return gaps


def _job_requirement_text(job: SavedJob) -> str:
    parts = [job.raw_jd_text]
    structured = job.structured_jd or {}
    for key in (
        "raw_snippet",
        "evidence_quotes",
        "responsibilities",
        "requirements",
        "required_skills",
        "must_have_skills",
        "preferred_skills",
    ):
        value = structured.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, str))
    return "\n".join(dict.fromkeys(item for item in parts if item))


def _first_pattern_match(
    patterns: tuple[str, ...], text: str
) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match is not None:
            return match
    return None


def _deterministic_questions(gaps: list[PreparationSkillGap]) -> list[PreparationQuestion]:
    items = []
    for gap in [item for item in gaps if item.evidence_status in {"partial", "unknown", "missing"}][:5]:
        prompt = f"Which description is closest to your current experience with {gap.skill}?"
        question_id = str(uuid5(NAMESPACE_URL, f"{gap.skill}:{prompt}"))
        dimension = (gap.dimensions or _default_capability_dimensions(gap.skill))[0]
        items.append(PreparationQuestion(
            question_id=question_id, skill=gap.skill, prompt=prompt,
            why_asked=f"The JD treats {gap.skill} as important, but current evidence is {gap.evidence_status}.",
            options=_fallback_options(gap),
            decision_objective=QuestionDecisionObjective(
                dimension_id=dimension.dimension_id,
                uncertainty=f"The candidate's current boundary for {dimension.label} is unresolved.",
                why_now=f"This dimension is required by {gap.skill} and lacks concrete evidence.",
            ),
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
        objective = raw.get("decision_objective")
        if require_model_options and (
            not isinstance(objective, dict)
            or not str(objective.get("dimension_id") or "").strip()
        ):
            raise ValueError(f"Question for {skill} needs a decision_objective")
        options = []
        for index, item in enumerate(raw_options or []):
            if not isinstance(item, dict):
                raise TypeError(f"Question option {index} for {skill} must be an object")
            option = {**item}
            if require_model_options and not str(item.get("answer_kind") or "").strip():
                raise ValueError(
                    f"Question option {index} for {skill} needs an answer_kind"
                )
            option.setdefault(
                "option_id",
                str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{skill}:{prompt}:{index}:{item.get('answer_kind', '')}",
                    )
                ),
            )
            option.setdefault(
                "decision_dimension",
                str(objective.get("dimension_id") or "model_semantic")
                if isinstance(objective, dict)
                else "model_semantic",
            )
            options.append(PreparationAnswerOption.model_validate(option))
        if require_model_options:
            objective_id = str(objective.get("dimension_id"))
            for option in options:
                if not option.state_effects:
                    raise ValueError(
                        f"Option {option.option_id} for {skill} needs state_effects"
                    )
                if not option.next_question_signal.strip():
                    raise ValueError(
                        f"Option {option.option_id} for {skill} needs next_question_signal"
                    )
                primary_effect = next(
                    (
                        effect for effect in option.state_effects
                        if effect.dimension_id == objective_id
                    ),
                    None,
                )
                expected_state = {
                    "evidence_claim": "partial",
                    "partial_practice": "partial",
                    "knowledge_gap": "knowledge_gap",
                    "explicit_absence": "missing",
                    "unclear": "unknown",
                }[option.answer_kind]
                if primary_effect is None or primary_effect.state != expected_state:
                    raise ValueError(
                        f"Option {option.option_id} for {skill} must update its primary "
                        f"objective to {expected_state}"
                    )
        questions.append(PreparationQuestion(
            question_id=str(uuid5(NAMESPACE_URL, f"{skill}:{prompt}")),
            skill=skill, prompt=prompt,
            why_asked=str(raw.get("why_asked") or "Clarifies an important evidence gap."),
            options=options,
            free_text_allowed=bool(raw.get("free_text_allowed", True)),
            free_text_prompt=str(raw.get("free_text_prompt") or (
                "If none of these options describes your situation accurately, explain what is different."
            )),
            decision_objective=raw.get("decision_objective"),
        ))
    return questions


def _fallback_options(gap: PreparationSkillGap) -> list[PreparationAnswerOption]:
    skill = gap.skill
    dimension = (gap.dimensions or _default_capability_dimensions(skill))[0].dimension_id
    options = [
        PreparationAnswerOption(
            option_id="delivered_result",
            value="work_experience",
            label=f"Delivered {skill} in professional work",
            description="I owned a relevant task or deliverable in a real work setting.",
            evidence_transition="partial",
            route="ask_evidence",
            detail_policy="required",
            follow_up_prompt="What did you personally own, and how was the result evaluated?",
            decision_dimension="delivery_ownership",
        ),
        PreparationAnswerOption(
            option_id="substantial_project",
            value="project_experience",
            label=f"Applied {skill} in a substantial project",
            description="I implemented or evaluated it in an academic, personal, or team project.",
            evidence_transition="partial",
            route="ask_evidence",
            detail_policy="required",
            follow_up_prompt="What did you implement personally, and what evidence shows how it worked?",
            decision_dimension="hands_on_implementation",
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
            decision_dimension="guided_practice_boundary",
        ),
        PreparationAnswerOption(
            option_id="concept_only",
            value="conceptual_only",
            label=f"Understand {skill} only conceptually",
            description="I know the main ideas but have not applied them hands-on.",
            evidence_transition="partial",
            route="learning",
            detail_policy="not_needed",
            decision_dimension="conceptual_depth",
        ),
        PreparationAnswerOption(
            option_id="no_current_experience",
            value="no_experience",
            label=f"No current experience with {skill}",
            description="I have not learned or used this capability yet.",
            evidence_transition="missing",
            route="capability_gap",
            detail_policy="not_needed",
            decision_dimension="current_capability_absence",
        ),
        PreparationAnswerOption(
            option_id="needs_context",
            value="uncertain",
            label="I need a more specific distinction",
            description="My situation overlaps multiple choices or the question is too broad.",
            evidence_transition="unknown",
            route="clarify",
            detail_policy="required",
            follow_up_prompt="What part of the choices does not fit your actual situation?",
            decision_dimension="unclassified_boundary",
        ),
    ]
    state_by_value = {
        "work_experience": "partial", "project_experience": "partial",
        "practice_only": "knowledge_gap", "conceptual_only": "knowledge_gap",
        "no_experience": "missing", "uncertain": "unknown",
    }
    return [item.model_copy(update={
        "state_effects": [OptionStateEffect(
            dimension_id=dimension, state=state_by_value[item.value]
        )],
        "next_question_signal": (
            "request_concrete_evidence" if item.route == "ask_evidence"
            else "replan_from_updated_state"
        ),
    }) for item in options]


def _default_capability_dimensions(skill: str) -> list[CapabilityDimension]:
    normalized = _normalized_skill(skill)
    catalog = {
        "ppg signal processing": ("motion_artifact_handling", "Motion artifact handling"),
        "ecg signal processing": ("qrs_and_noise_processing", "QRS detection and noise handling"),
        "acc motion signal analysis": ("motion_context_analysis", "Motion context and artifact analysis"),
        "blood pressure estimation": ("calibration_and_validation", "Calibration and subject-independent validation"),
        "multimodal physiological signal fusion": ("alignment_and_fusion", "Time alignment and fusion architecture"),
    }
    key, label = catalog.get(normalized, (f"{normalized.replace(' ', '_')}_boundary", f"{skill} decision boundary"))
    return [CapabilityDimension(dimension_id=key, label=label)]


def _question_generation_memory(
    job: SavedJob,
    profile: ResumeProfile | None,
    analysis: SavedJobAnalysis | None,
    fallback_gaps: list[PreparationSkillGap],
) -> dict[str, object]:
    coverage = [item for item in fallback_gaps if item.evidence_status != "supported"][:5]
    return {
        "cache_context": {
            "job": {
                "title": job.title,
                "company": job.company,
                "raw_jd_text": job.raw_jd_text,
            },
            "candidate_profile": _compact_profile_context(profile),
        },
        "stage_contract": {
            "stage": "initial_capability_map_and_two_questions",
            "absence_rule": (
                "Missing profile evidence means unresolved, never explicit absence."
            ),
            "model_output": (
                "Return business semantics only. The backend derives execution routes."
            ),
        },
        "analysis_summary": _compact_analysis_context(analysis),
        "gap_anchors": [_compact_gap_context(item) for item in fallback_gaps],
        "required_coverage_memory": {
            "skills": [item.skill for item in coverage[:2]],
            "additional_candidates": [item.skill for item in coverage[2:]],
            "minimum_question_count": min(2, len(coverage)),
            "rule": "Cover skills first; use additional_candidates only when useful.",
        },
    }


def _next_question_memory(
    all_gaps: list[PreparationSkillGap],
    remaining_gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
    answers: list[PreparationAnswer],
) -> dict[str, object]:
    return {
        "cache_context": {
            "capability_contract": [
                {
                    "skill": gap.skill,
                    "importance": gap.importance,
                    "jd_evidence": gap.jd_evidence,
                    "profile_evidence": gap.profile_evidence,
                    "dimensions": [
                        {"dimension_id": item.dimension_id, "label": item.label}
                        for item in gap.dimensions
                    ],
                }
                for gap in all_gaps
            ],
            "initial_locked_questions": [
                _compact_question_context(item, include_options=True)
                for item in questions[:2]
            ],
        },
        "stage_contract": {
            "stage": "generate_exactly_one_next_question",
            "rule": "Never rewrite a locked question or repeat its decision objective.",
        },
        "dynamic_state": {
            "remaining_gap_state": [
                {
                    "skill": gap.skill,
                    "dimensions": [item.model_dump(mode="json") for item in gap.dimensions],
                }
                for gap in remaining_gaps
            ],
            "locked_objectives": [
                _compact_question_context(item, include_options=False)
                for item in questions
            ],
            "committed_answers": _compact_answer_context(
                questions, [item for item in answers if item.committed]
            ),
        },
    }


def _recommendation_memory(
    gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
    answers: list[PreparationAnswer],
    fallback: list[PreparationRecommendation],
) -> dict[str, object]:
    return {
        "final_capability_state": [
            {
                "skill": gap.skill,
                "importance": gap.importance,
                "skill_type": gap.skill_type,
                "evidence_status": gap.evidence_status,
                "evidence_origin": gap.evidence_origin,
                "dimensions": [item.model_dump(mode="json") for item in gap.dimensions],
            }
            for gap in gaps
        ],
        "candidate_answer_evidence": _compact_answer_context(questions, answers),
        "output_limits": {
            "maximum_recommendations": min(6, max(1, len(fallback))),
            "allowed_action_types": [
                "learning", "experience_inventory", "interview_story", "capability_gap"
            ],
        },
    }


def _compact_profile_context(profile: ResumeProfile | None) -> dict[str, object] | None:
    if profile is None:
        return None
    return {
        "summary": profile.summary,
        "target_roles": profile.target_roles,
        "target_directions": profile.target_directions,
        "core_skills": profile.core_skills,
        "supporting_skills": profile.supporting_skills,
        "strengths": profile.strengths,
        "risks": profile.risks,
        "evidence_detail": profile.profile or profile.raw_resume_text,
    }


def _compact_analysis_context(
    analysis: SavedJobAnalysis | None,
) -> dict[str, object] | None:
    if analysis is None:
        return None
    return {
        "match_score": analysis.match_score,
        "confidence_label": analysis.confidence_label,
        "recommendation": analysis.recommendation,
        "matched_strengths": analysis.matched_strengths,
        "critical_gaps": analysis.critical_gaps,
        "resume_actions": analysis.resume_actions,
    }


def _compact_gap_context(gap: PreparationSkillGap) -> dict[str, object]:
    return {
        "skill": gap.skill,
        "importance": gap.importance,
        "evidence_status": gap.evidence_status,
        "skill_type": gap.skill_type,
        "jd_evidence": gap.jd_evidence,
        "profile_evidence": gap.profile_evidence,
        "rationale": gap.rationale,
        "dimensions": [item.model_dump(mode="json") for item in gap.dimensions],
    }


def _compact_question_context(
    question: PreparationQuestion, *, include_options: bool
) -> dict[str, object]:
    result: dict[str, object] = {
        "question_id": question.question_id,
        "skill": question.skill,
        "prompt": question.prompt,
        "decision_objective": (
            question.decision_objective.model_dump(mode="json")
            if question.decision_objective else None
        ),
    }
    if include_options:
        result["options"] = [
            {
                "option_id": option.option_id,
                "answer_kind": option.answer_kind,
                "label": option.label,
                "description": option.description,
                "state_effects": [
                    item.model_dump(mode="json") for item in option.state_effects
                ],
                "next_question_signal": option.next_question_signal,
            }
            for option in question.options
        ]
    return result


def _compact_answer_context(
    questions: list[PreparationQuestion], answers: list[PreparationAnswer]
) -> list[dict[str, object]]:
    question_by_id = {item.question_id: item for item in questions}
    result = []
    for answer in answers:
        question = question_by_id.get(answer.question_id)
        option = next(
            (
                item for item in question.options
                if item.option_id == answer.selected_option_id
            ),
            None,
        ) if question else None
        result.append({
            "question_id": answer.question_id,
            "skill": question.skill if question else None,
            "dimension_id": (
                question.decision_objective.dimension_id
                if question and question.decision_objective else None
            ),
            "selected_option_id": answer.selected_option_id,
            "selected_option_label": option.label if option else None,
            "answer_kind": option.answer_kind if option else None,
            "detail": answer.detail,
            "free_text": answer.free_text or answer.answer,
            "detail_quality": answer.detail_quality,
            "evidence_transition": answer.evidence_transition,
            "route": answer.route,
            "committed": answer.committed,
        })
    return result


def _json_prompt(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _validate_question_coverage(
    seed_gaps: list[PreparationSkillGap],
    model_gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
) -> None:
    unresolved = {"partial", "unknown", "missing"}
    coverage_seeds = [
        item for item in seed_gaps if item.evidence_status in unresolved
    ][:5]
    minimum = min(2, len(coverage_seeds))
    if len(questions) < minimum:
        raise ValueError(
            f"Question coverage is too small: expected at least {minimum}, "
            f"got {len(questions)}"
        )

    question_skills = [_normalized_skill(item.skill) for item in questions]
    if len(question_skills) != len(set(question_skills)):
        raise ValueError("Questions must cover distinct skills")

    model_gap_skills = {_normalized_skill(item.skill) for item in model_gaps}
    orphaned = [
        item.skill
        for item in questions
        if _normalized_skill(item.skill) not in model_gap_skills
    ]
    if orphaned:
        raise ValueError(f"Questions without matching skill gaps: {orphaned}")

    gaps_by_skill = {_normalized_skill(item.skill): item for item in model_gaps}
    objective_ids = []
    for question in questions:
        gap = gaps_by_skill[_normalized_skill(question.skill)]
        valid_dimensions = {item.dimension_id for item in gap.dimensions}
        objective = question.decision_objective
        if objective is None or objective.dimension_id not in valid_dimensions:
            raise ValueError(
                f"Question for {question.skill} must target one declared capability dimension"
            )
        objective_ids.append(objective.dimension_id)
        if any(
            effect.dimension_id not in valid_dimensions
            for option in question.options for effect in option.state_effects
        ):
            raise ValueError(
                f"Question for {question.skill} updates an undeclared capability dimension"
            )
    if len(objective_ids) != len(set(objective_ids)):
        raise ValueError("Initial questions must target distinct decision objectives")

    missing = [
        item.skill
        for item in coverage_seeds[:minimum]
        if _normalized_skill(item.skill) not in question_skills
    ]
    if missing:
        raise ValueError(f"Missing required JD coverage: {missing}")

    high_priority = [
        item
        for item in model_gaps
        if item.importance == "high" and item.evidence_status in unresolved
    ][:minimum]
    missing_high = [
        item.skill
        for item in high_priority
        if _normalized_skill(item.skill) not in question_skills
    ]
    if missing_high:
        raise ValueError(f"High-priority gaps lack questions: {missing_high}")

    for question in questions:
        _validate_question_not_generic(question, [])


def _validate_question_not_generic(
    question: PreparationQuestion,
    locked_questions: list[PreparationQuestion],
) -> None:
    if question.decision_objective is None:
        raise ValueError(f"Question for {question.skill} lacks a decision objective")
    effect_signatures = {
        tuple(sorted((effect.dimension_id, effect.state) for effect in option.state_effects))
        for option in question.options
    }
    if len(effect_signatures) < 2:
        raise ValueError(
            f"Question for {question.skill} does not produce contrasting state updates"
        )
    for locked in locked_questions:
        if (
            locked.decision_objective is not None
            and locked.decision_objective.dimension_id
            == question.decision_objective.dimension_id
        ):
            raise ValueError("Next question repeats a locked decision objective")


def _normalized_skill(value: str) -> str:
    return " ".join(
        re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", value.casefold())
    )


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
            has_specific_evidence = answer is not None and answer.detail_quality == "specific"
            action = (
                f"Turn the supported {gap.skill} example into a concise context-action-result story."
                if has_specific_evidence
                else f"Inventory the missing method, personal contribution, and result for the user-reported {gap.skill} example."
            )
            basis = [detail[:300]] if detail else [f"User selected {level.replace('_', ' ')}."]
            action_type = "interview_story" if has_specific_evidence else "experience_inventory"
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
