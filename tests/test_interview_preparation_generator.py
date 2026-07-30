"""回归验证面试准备的正常链路、失败边界和兼容契约。"""

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
    _next_question_memory,
    generate_preparation_questions,
    generate_next_preparation_question,
    generate_recommendations,
    resolve_preparation_answers,
)
from app.services.llm_service import LLMServiceError


class SequenceLLM:
    """为当前测试场景提供 SequenceLLM 夹具或替身。"""
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.system_prompts: list[str] = []
        self.user_prompts: list[str] = []

    def chat_completion_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        expected_root_key: str | None = None,
    ) -> dict:
        """提供 SequenceLLM.chat_completion_json 所需的测试行为。"""
        self.system_prompts.append(system_prompt)
        self.user_prompts.append(user_prompt)
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
    dimension = f"{skill.lower().replace(' ', '_')}_boundary"
    return {
        "skill": skill,
        "importance": "high",
        "evidence_status": "unknown",
        "skill_type": "knowledge",
        "jd_evidence": f"The JD requires {skill}.",
        "profile_evidence": [],
        "rationale": "No concrete profile evidence.",
        "dimensions": [{
            "dimension_id": dimension,
            "label": f"{skill} technical boundary",
            "state": "unresolved",
            "evidence": [],
        }],
    }


def _question(skill: str) -> dict[str, object]:
    dimension = f"{skill.lower().replace(' ', '_')}_boundary"
    return {
        "skill": skill,
        "prompt": f"Which description best matches your {skill} experience?",
        "why_asked": "The current level is unknown.",
        "decision_objective": {
            "dimension_id": dimension,
            "uncertainty": "The technical boundary is unresolved.",
            "why_now": "It changes preparation advice.",
        },
        "options": [
            {
                "option_id": f"implemented_{skill}",
                "answer_kind": "evidence_claim",
                "label": f"Implemented {skill}",
                "description": "I implemented and evaluated relevant processing.",
                "follow_up_prompt": "What did you implement and how did you evaluate it?",
                "state_effects": [{"dimension_id": dimension, "state": "partial"}],
                "next_question_signal": "verify_evaluation_method",
            },
            {
                "option_id": f"concept_{skill}",
                "answer_kind": "knowledge_gap",
                "label": "Conceptual understanding only",
                "description": "I understand it but have not implemented it.",
                "follow_up_prompt": None,
                "state_effects": [{"dimension_id": dimension, "state": "knowledge_gap"}],
                "next_question_signal": "close_with_learning_task",
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
    assert len(questions) == 2
    assert stage.mode == "llm"
    assert stage.attempts == 2
    assert stage.attempt_errors == [
        "LLMServiceError: LLM JSON output must be an object"
    ]
    assert "exactly one JSON object" in llm.system_prompts[0]
    assert "FORMAT CORRECTION" in llm.system_prompts[1]
    initial_memory = __import__("json").loads(llm.user_prompts[0])
    assert list(initial_memory) == [
        "cache_context",
        "stage_contract",
        "analysis_summary",
        "gap_anchors",
        "required_coverage_memory",
    ]
    assert "jd_anchor_memory" not in initial_memory
    assert "gap_state_memory" not in initial_memory


def test_model_business_semantics_are_mapped_to_backend_protocol_once() -> None:
    question_payload = _question("PPG signal processing")
    llm = SequenceLLM([{
        "skill_gaps": [_gap("PPG signal processing")],
        "questions": [question_payload],
    }])
    job = _job().model_copy(update={"raw_jd_text": "Process PPG signals."})

    _, questions, stage = generate_preparation_questions(
        job, None, None, llm_service=llm
    )

    assert stage.mode == "llm"
    assert stage.attempts == 1
    claim, learning = questions[0].options
    assert (claim.value, claim.evidence_transition, claim.route) == (
        "project_experience", "partial", "ask_evidence"
    )
    assert claim.detail_policy == "required"
    assert (learning.value, learning.evidence_transition, learning.route) == (
        "conceptual_only", "partial", "learning"
    )
    assert learning.detail_policy == "not_needed"


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

    assert len(questions) == 2
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
    assert len(questions) == 2
    assert stage.mode == "deterministic"


def test_next_question_uses_committed_memory_and_does_not_rewrite_locked_questions() -> None:
    gaps = [
        PreparationSkillGap.model_validate(_gap(skill))
        for skill in ("PPG signal processing", "ECG signal processing")
    ]
    locked = PreparationQuestion.model_validate({
        **_question("PPG signal processing"), "question_id": "q1"
    })
    next_question = _question("ECG signal processing")
    next_question["options"] = list(reversed(next_question["options"]))
    llm = SequenceLLM([{"question": next_question}])

    question, stage = generate_next_preparation_question(
        gaps,
        [locked],
        [PreparationAnswer(
            question_id="q1", selected_option_id=locked.options[1].option_id,
            committed=True,
        )],
        llm_service=llm,
    )

    assert question is not None
    assert question.skill == "ECG signal processing"
    assert stage.mode == "llm"
    memory = __import__("json").loads(llm.user_prompts[0])
    assert list(memory) == ["cache_context", "stage_contract", "dynamic_state"]
    assert "locked_questions" not in memory["dynamic_state"]


def test_next_question_can_revisit_a_skill_for_another_unresolved_dimension() -> None:
    gap_payload = _gap("PPG signal processing")
    gap_payload["dimensions"] = [
        {"dimension_id": "artifact_handling", "label": "Artifact handling", "state": "partial", "evidence": []},
        {"dimension_id": "quality_evaluation", "label": "Quality evaluation", "state": "unresolved", "evidence": []},
    ]
    gap = PreparationSkillGap.model_validate(gap_payload)
    locked_payload = _question("PPG signal processing")
    locked_payload["question_id"] = "q1"
    locked_payload["decision_objective"]["dimension_id"] = "artifact_handling"
    for index, option in enumerate(locked_payload["options"]):
        option["state_effects"] = [{"dimension_id": "artifact_handling", "state": "partial" if index == 0 else "knowledge_gap"}]
    locked = PreparationQuestion.model_validate(locked_payload)
    next_payload = _question("PPG signal processing")
    next_payload["decision_objective"]["dimension_id"] = "quality_evaluation"
    for index, option in enumerate(next_payload["options"]):
        option["state_effects"] = [{"dimension_id": "quality_evaluation", "state": "partial" if index == 0 else "knowledge_gap"}]
    llm = SequenceLLM([{"question": next_payload}])

    question, stage = generate_next_preparation_question(
        [gap], [locked], [], llm_service=llm
    )

    assert stage.mode == "llm"
    assert question is not None
    assert question.skill == "PPG signal processing"
    assert question.decision_objective.dimension_id == "quality_evaluation"


def test_next_question_cache_prefix_excludes_mutable_gap_state() -> None:
    gap = PreparationSkillGap.model_validate(_gap("PPG signal processing"))
    changed = gap.model_copy(update={
        "skill_type": "experience",
        "dimensions": [
            item.model_copy(update={"state": "knowledge_gap", "evidence": ["answer"]})
            for item in gap.dimensions
        ],
    })
    question = PreparationQuestion.model_validate({
        **_question("PPG signal processing"), "question_id": "q1"
    })

    before = _next_question_memory([gap], [gap], [question], [])
    after = _next_question_memory([changed], [changed], [question], [])

    assert before["cache_context"] == after["cache_context"]
    assert before["dynamic_state"] != after["dynamic_state"]


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

    legacy_gap = PreparationSkillGap.model_validate({
        **_gap("PPG signal processing"),
        "dimensions": [{
            "dimension_id": "motion_artifact_handling",
            "label": "Motion artifact handling",
            "state": "demonstrated",
            "evidence": ["legacy"],
        }],
    })
    assert legacy_gap.dimensions[0].state == "supported"


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
    recommendation_memory = __import__("json").loads(llm.user_prompts[0])
    assert "questions" not in recommendation_memory
    assert "deterministic_baseline" not in recommendation_memory


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
