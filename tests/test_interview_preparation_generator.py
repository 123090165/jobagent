from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.interview_preparation import (
    PreparationAnswer,
    PreparationAnswerOption,
    PreparationQuestion,
    PreparationSkillGap,
)
from app.schemas.saved_job import SavedJob
from app.services.interview_preparation_generator import (
    generate_preparation_questions,
    generate_recommendations,
    resolve_preparation_answers,
)
from app.services.llm_service import LLMServiceError


class SequenceLLM:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.system_prompts: list[str] = []

    def chat_completion_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        expected_root_key: str | None = None,
    ) -> dict:
        self.system_prompts.append(system_prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response  # type: ignore[return-value]


def _job() -> SavedJob:
    now = datetime.now(timezone.utc)
    return SavedJob(
        saved_job_id="job-1",
        user_id="user-1",
        title="AI Health Algorithm Engineer",
        company="Example",
        raw_jd_text=(
            "Process PPG, ECG, and ACC signals. Develop blood-pressure estimation "
            "and multimodal fusion models with PyTorch."
        ),
        first_seen_at=now,
        saved_at=now,
        updated_at=now,
    )


def _gap(skill: str) -> dict[str, object]:
    return {
        "skill": skill,
        "importance": "high",
        "evidence_status": "unknown",
        "skill_type": "knowledge",
        "jd_evidence": f"The JD requires {skill}.",
        "profile_evidence": [],
        "rationale": "No concrete profile evidence.",
    }


def _question(skill: str) -> dict[str, object]:
    return {
        "skill": skill,
        "prompt": f"Which description best matches your {skill} experience?",
        "why_asked": "The current level is unknown.",
        "options": [
            {
                "option_id": f"implemented_{skill}",
                "value": "project_experience",
                "label": f"Implemented {skill}",
                "description": "I implemented and evaluated relevant processing.",
                "evidence_transition": "partial",
                "route": "ask_evidence",
                "detail_policy": "required",
                "follow_up_prompt": "What did you implement and how did you evaluate it?",
                "decision_dimension": "hands_on_implementation",
            },
            {
                "option_id": f"concept_{skill}",
                "value": "conceptual_only",
                "label": "Conceptual understanding only",
                "description": "I understand it but have not implemented it.",
                "evidence_transition": "partial",
                "route": "learning",
                "detail_policy": "not_needed",
                "decision_dimension": "conceptual_vs_hands_on",
            },
        ],
    }


def test_question_generation_retries_schema_output_and_records_attempts() -> None:
    llm = SequenceLLM([
        LLMServiceError("LLM JSON output must be an object"),
        {
            "skill_gaps": [
                _gap(skill)
                for skill in (
                    "blood pressure estimation",
                    "multimodal physiological signal fusion",
                    "PPG signal processing",
                )
            ],
            "questions": [
                _question(skill)
                for skill in (
                    "blood pressure estimation",
                    "multimodal physiological signal fusion",
                    "PPG signal processing",
                )
            ],
        },
    ])

    gaps, questions, stage = generate_preparation_questions(
        _job(), None, None, llm_service=llm
    )

    assert {item.skill for item in gaps} >= {"PPG signal processing"}
    assert {item.skill for item in questions} >= {"PPG signal processing"}
    assert stage.mode == "llm"
    assert stage.attempts == 2
    assert stage.attempt_errors == [
        "LLMServiceError: LLM JSON output must be an object"
    ]
    assert "root MUST be one object" in llm.system_prompts[0]
    assert "FORMAT CORRECTION" in llm.system_prompts[1]


def test_question_generation_retries_when_required_jd_coverage_is_missing() -> None:
    complete = {
        "skill_gaps": [
            _gap(skill)
            for skill in (
                "blood pressure estimation",
                "multimodal physiological signal fusion",
                "PPG signal processing",
            )
        ],
        "questions": [
            _question(skill)
            for skill in (
                "blood pressure estimation",
                "multimodal physiological signal fusion",
                "PPG signal processing",
            )
        ],
    }
    llm = SequenceLLM([
        {
            "skill_gaps": [_gap("PPG signal processing")],
            "questions": [_question("PPG signal processing")],
        },
        complete,
    ])

    _, questions, stage = generate_preparation_questions(
        _job(), None, None, llm_service=llm
    )

    assert len(questions) == 3
    assert stage.mode == "llm"
    assert stage.attempts == 2
    assert "Question coverage is too small" in stage.attempt_errors[0]
    assert "Question coverage is too small" in llm.system_prompts[1]


def test_deterministic_coverage_uses_structured_jd_evidence_quotes() -> None:
    job = _job().model_copy(update={
        "raw_jd_text": "Develop physiological-signal algorithms.",
        "structured_jd": {
            "evidence_quotes": [
                "Fuse PPG, ECG, and ACC signals for blood-pressure estimation."
            ]
        },
    })

    gaps, questions, stage = generate_preparation_questions(
        job, None, None, llm_service=None
    )

    skills = {item.skill for item in gaps}
    assert {
        "PPG signal processing",
        "ECG signal processing",
        "ACC motion signal analysis",
        "blood pressure estimation",
    } <= skills
    assert len(questions) >= 3
    assert stage.mode == "deterministic"


def test_free_text_is_classified_to_a_question_option_without_rewriting_it() -> None:
    question = PreparationQuestion(
        question_id="q1",
        skill="PPG signal processing",
        prompt="Choose the closest description.",
        why_asked="Clarifies evidence.",
        options=[
            PreparationAnswerOption(
                option_id="adjacent_only",
                value="uncertain",
                label="Adjacent experience only",
                description="The boundary needs clarification.",
                evidence_transition="unknown",
                route="clarify",
                detail_policy="optional",
            ),
            PreparationAnswerOption(
                option_id="concept_only",
                value="conceptual_only",
                label="Concept only",
                description="No hands-on use.",
                evidence_transition="partial",
                route="learning",
                detail_policy="not_needed",
            ),
        ],
    )
    llm = SequenceLLM([{
        "classifications": [{
            "question_id": "q1",
            "option_id": "adjacent_only",
            "reason": "The response describes adjacent signal work only.",
        }]
    }])
    raw = "I processed ECG signals, but the PPG-specific part was handled by someone else."

    answers = resolve_preparation_answers(
        [question],
        [PreparationAnswer(question_id="q1", response_mode="free_text", free_text=raw)],
        llm_service=llm,
    )

    assert answers[0].free_text == raw
    assert answers[0].selected_option_id == "adjacent_only"
    assert answers[0].experience_level == "uncertain"
    assert answers[0].route == "clarify"
    assert answers[0].resolution_source == "llm_classified"


def test_free_text_is_not_classified_when_session_is_only_saved() -> None:
    question = PreparationQuestion(
        question_id="q1",
        skill="PPG",
        prompt="Choose the closest description.",
        why_asked="Clarifies evidence.",
        options=[PreparationAnswerOption(
            option_id="needs_context",
            value="uncertain",
            label="Needs context",
            description="The choices do not fit.",
            evidence_transition="unknown",
            route="clarify",
            detail_policy="optional",
        )],
    )
    llm = SequenceLLM([])

    answers = resolve_preparation_answers(
        [question],
        [PreparationAnswer(question_id="q1", response_mode="free_text", free_text="A boundary")],
        llm_service=llm,
        classify_free_text=False,
    )

    assert answers[0].selected_option_id is None
    assert answers[0].resolution_source is None
    assert llm.responses == []


def test_legacy_option_is_upgraded_with_safe_transition_defaults() -> None:
    option = PreparationAnswerOption.model_validate({
        "value": "no_experience",
        "label": "No experience",
        "description": "I have not used this.",
    })

    assert option.option_id == "no_experience"
    assert option.evidence_transition == "missing"
    assert option.route == "capability_gap"

    project = PreparationAnswerOption.model_validate({
        "value": "project_experience",
        "label": "Project experience",
        "description": "I used it in a project.",
    })
    assert project.evidence_transition == "partial"
    assert project.route == "ask_evidence"


def test_recommendation_prompt_requires_object_root_and_complete_schema() -> None:
    llm = SequenceLLM([{
        "recommendations": [{
            "title": "Review blood-pressure estimation",
            "action": "Implement and evaluate one small baseline without claiming prior experience.",
            "action_type": "learning",
            "skill": "blood-pressure estimation",
            "evidence_basis": ["The candidate selected conceptual understanding."],
        }]
    }])
    gap = PreparationSkillGap(
        skill="blood-pressure estimation",
        importance="high",
        evidence_status="partial",
        skill_type="knowledge",
        jd_evidence="Develop blood-pressure estimation models.",
        rationale="The candidate lacks hands-on evidence.",
    )
    question = PreparationQuestion(
        question_id="q1",
        skill=gap.skill,
        prompt="Choose your current level.",
        why_asked="Clarifies the gap.",
    )
    answer = PreparationAnswer(
        question_id="q1",
        experience_level="conceptual_only",
    )

    recommendations, stage = generate_recommendations(
        [gap], [question], [answer], llm_service=llm
    )

    assert recommendations[0].action_type == "learning"
    assert stage.mode == "llm"
    assert stage.attempts == 1
    assert '"recommendations"' in llm.system_prompts[0]
    assert "Never return a top-level array" in llm.system_prompts[0]


def test_deterministic_recommendation_does_not_turn_vague_claim_into_story() -> None:
    gap = PreparationSkillGap(
        skill="ECG signal processing",
        importance="high",
        evidence_status="partial",
        skill_type="experience",
        jd_evidence="Process ECG signals.",
        rationale="Concrete evidence is incomplete.",
    )
    question = PreparationQuestion(
        question_id="q1",
        skill=gap.skill,
        prompt="Choose your current level.",
        why_asked="Clarifies the evidence.",
    )
    answer = PreparationAnswer(
        question_id="q1",
        experience_level="project_experience",
        detail="I have some ECG project experience.",
        detail_quality="vague",
        evidence_transition="partial",
        route="next_skill",
    )

    recommendations, stage = generate_recommendations(
        [gap], [question], [answer], llm_service=None
    )

    assert stage.mode == "deterministic"
    assert recommendations[0].action_type == "experience_inventory"
    assert "missing method" in recommendations[0].action
