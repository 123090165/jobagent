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


def test_question_generation_retries_schema_output_and_records_attempts() -> None:
    llm = SequenceLLM([
        LLMServiceError("LLM JSON output must be an object"),
        {
            "skill_gaps": [{
                "skill": "PPG signal processing",
                "importance": "high",
                "evidence_status": "unknown",
                "skill_type": "knowledge",
                "jd_evidence": "Process PPG signals.",
                "profile_evidence": [],
                "rationale": "No concrete profile evidence.",
            }],
            "questions": [{
                "skill": "PPG signal processing",
                "prompt": "Which description best matches your PPG experience?",
                "why_asked": "The current level is unknown.",
                "options": [
                    {
                        "option_id": "implemented_pipeline",
                        "value": "project_experience",
                        "label": "Implemented a PPG pipeline",
                        "description": "I implemented and evaluated relevant processing.",
                        "evidence_transition": "supported",
                        "route": "ask_evidence",
                        "detail_policy": "required",
                        "follow_up_prompt": "What did you implement and how did you evaluate it?",
                    },
                    {
                        "option_id": "concept_only",
                        "value": "conceptual_only",
                        "label": "Conceptual understanding only",
                        "description": "I understand it but have not implemented it.",
                        "evidence_transition": "partial",
                        "route": "learning",
                        "detail_policy": "not_needed",
                    },
                ],
            }],
        },
    ])

    gaps, questions, stage = generate_preparation_questions(
        _job(), None, None, llm_service=llm
    )

    assert gaps[0].skill == "PPG signal processing"
    assert questions[0].skill == "PPG signal processing"
    assert stage.mode == "llm"
    assert stage.attempts == 2
    assert stage.attempt_errors == [
        "LLMServiceError: LLM JSON output must be an object"
    ]
    assert "root MUST be one object" in llm.system_prompts[0]
    assert "FORMAT CORRECTION" in llm.system_prompts[1]


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


def test_legacy_option_is_upgraded_with_safe_transition_defaults() -> None:
    option = PreparationAnswerOption.model_validate({
        "value": "no_experience",
        "label": "No experience",
        "description": "I have not used this.",
    })

    assert option.option_id == "no_experience"
    assert option.evidence_transition == "missing"
    assert option.route == "capability_gap"


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
