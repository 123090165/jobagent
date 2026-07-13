from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.application.saved_job_usecases import (
    complete_interview_preparation,
    generate_interview_preparation,
)
from app.schemas.interview_preparation import (
    PreparationAnswer,
    PreparationAnswerRequest,
    PreparationGenerateRequest,
)
from experiments.preparation_eval.model import EvaluationModel
from experiments.preparation_eval.schemas import (
    CandidatePersona,
    CandidateSelfAssessment,
    CandidateTurn,
    PreparationEvaluationReport,
    RuleCheck,
)

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


class EvaluationState(TypedDict, total=False):
    user_id: str
    profile_id: str
    saved_job_id: str
    profile_memory: dict[str, object]
    job_context: dict[str, object]
    persona_memory: dict[str, object]
    preparation: dict[str, object]
    question_index: int
    answers: list[dict[str, object]]
    episodic_memory: list[dict[str, object]]
    paused_once: bool
    self_assessment: dict[str, object]
    rule_checks: list[dict[str, object]]


class PreparationEvaluationAgent:
    def __init__(
        self,
        model: EvaluationModel,
        *,
        preparation_provider: str = "deepseek",
        persona_archetype: str = "calibrated but imperfect",
        pause_after: int = 2,
        finish_session: bool = True,
    ) -> None:
        self.model = model
        self.preparation_provider = preparation_provider
        self.persona_archetype = persona_archetype
        self.pause_after = max(0, pause_after)
        self.finish_session = finish_session
        self._graph = self._build_graph()

    async def run(
        self,
        *,
        user_id: str,
        profile_id: str,
        saved_job_id: str,
        profile_memory: dict[str, object],
        job_context: dict[str, object],
        saved_job_origin_id: str | None = None,
        association_method: str = "explicit_profile",
    ) -> PreparationEvaluationReport:
        state = await self._graph.ainvoke({
            "user_id": user_id,
            "profile_id": profile_id,
            "saved_job_id": saved_job_id,
            "profile_memory": profile_memory,
            "job_context": job_context,
            "question_index": 0,
            "answers": [],
            "episodic_memory": [],
            "paused_once": False,
        })
        checks = [RuleCheck.model_validate(item) for item in state["rule_checks"]]
        return PreparationEvaluationReport(
            evaluation_id=str(uuid4()),
            generated_at=datetime.now(timezone.utc),
            profile_id=profile_id,
            saved_job_id=saved_job_id,
            user_id=user_id,
            saved_job_origin_id=saved_job_origin_id,
            association_method=association_method,
            evaluation_model=self.model.model_name,
            preparation_provider=self.preparation_provider,
            profile_memory=profile_memory,
            persona_memory=CandidatePersona.model_validate(state["persona_memory"]),
            episodic_memory=[CandidateTurn.model_validate(item) for item in state["episodic_memory"]],
            preparation_result=state["preparation"],
            self_assessment=CandidateSelfAssessment.model_validate(state["self_assessment"]),
            rule_checks=checks,
            passed=all(item.passed for item in checks),
        )

    def _build_graph(self):
        builder = StateGraph(EvaluationState)
        builder.add_node("build_persona", self._build_persona)
        builder.add_node("start_preparation", self._start_preparation)
        builder.add_node("answer_question", self._answer_question)
        builder.add_node("pause_preparation", self._pause_preparation)
        builder.add_node("finish_preparation", self._finish_preparation)
        builder.add_node("self_reflect", self._self_reflect)
        builder.add_node("rule_checks", self._rule_checks)
        builder.add_edge(START, "build_persona")
        builder.add_edge("build_persona", "start_preparation")
        builder.add_edge("start_preparation", "answer_question")
        builder.add_conditional_edges(
            "answer_question",
            self._route_after_answer,
            {
                "answer": "answer_question",
                "pause": "pause_preparation",
                "finish": "finish_preparation",
            },
        )
        builder.add_edge("pause_preparation", "answer_question")
        builder.add_edge("finish_preparation", "self_reflect")
        builder.add_edge("self_reflect", "rule_checks")
        builder.add_edge("rule_checks", END)
        return builder.compile()

    def _build_persona(self, state: EvaluationState) -> EvaluationState:
        response = self.model.generate_json(
            system_prompt=_prompt("persona_system.md"),
            user_prompt=_json_prompt({
                "requested_archetype": self.persona_archetype,
                "profile_memory": state["profile_memory"],
                "job_context": state["job_context"],
            }),
        )
        persona = CandidatePersona.model_validate(response)
        return {"persona_memory": persona.model_dump(mode="json")}

    async def _start_preparation(self, state: EvaluationState) -> EvaluationState:
        workspace = await generate_interview_preparation(
            state["saved_job_id"],
            PreparationGenerateRequest(
                resume_profile_id=state["profile_id"],
                llm_provider=self.preparation_provider,
            ),
            user_id=state["user_id"],
        )
        return {"preparation": workspace.model_dump(mode="json")}

    def _answer_question(self, state: EvaluationState) -> EvaluationState:
        questions = state["preparation"]["questions"]
        index = state.get("question_index", 0)
        question = questions[index]
        response = self.model.generate_json(
            system_prompt=_prompt("candidate_system.md"),
            user_prompt=_json_prompt({
                "profile_memory": state["profile_memory"],
                "persona_memory": state["persona_memory"],
                "episodic_memory": state.get("episodic_memory", []),
                "job_context": state["job_context"],
                "current_question": question,
            }),
        )
        turn = CandidateTurn.model_validate({
            **response,
            "question_id": question["question_id"],
            "skill": question["skill"],
        })
        valid_options = {item["value"] for item in question.get("options", [])}
        if turn.experience_level not in valid_options:
            raise ValueError(f"Evaluation model selected an unavailable option: {turn.experience_level}")
        answer = PreparationAnswer(
            question_id=turn.question_id,
            experience_level=turn.experience_level,
            detail=turn.detail,
        )
        return {
            "answers": [*state.get("answers", []), answer.model_dump(mode="json")],
            "episodic_memory": [
                *state.get("episodic_memory", []), turn.model_dump(mode="json")
            ],
            "question_index": index + 1,
        }

    def _route_after_answer(self, state: EvaluationState) -> str:
        answered = state.get("question_index", 0)
        total = len(state["preparation"]["questions"])
        if answered >= total:
            return "finish"
        if self.pause_after and answered >= self.pause_after and not state.get("paused_once"):
            return "pause"
        return "answer"

    async def _pause_preparation(self, state: EvaluationState) -> EvaluationState:
        workspace = await complete_interview_preparation(
            state["saved_job_id"],
            PreparationAnswerRequest(
                answers=[PreparationAnswer.model_validate(item) for item in state["answers"]],
                action="save",
                llm_provider=self.preparation_provider,
            ),
            user_id=state["user_id"],
        )
        return {
            "preparation": workspace.model_dump(mode="json"),
            "paused_once": True,
        }

    async def _finish_preparation(self, state: EvaluationState) -> EvaluationState:
        action = "complete" if self.finish_session else "stop"
        workspace = await complete_interview_preparation(
            state["saved_job_id"],
            PreparationAnswerRequest(
                answers=[PreparationAnswer.model_validate(item) for item in state["answers"]],
                action=action,
                llm_provider=self.preparation_provider,
            ),
            user_id=state["user_id"],
        )
        return {"preparation": workspace.model_dump(mode="json")}

    def _self_reflect(self, state: EvaluationState) -> EvaluationState:
        response = self.model.generate_json(
            system_prompt=_prompt("reflection_system.md"),
            user_prompt=_json_prompt({
                "profile_memory": state["profile_memory"],
                "persona_memory": state["persona_memory"],
                "episodic_memory": state["episodic_memory"],
                "job_context": state["job_context"],
                "preparation_result": state["preparation"],
            }),
        )
        assessment = CandidateSelfAssessment.model_validate(response)
        return {"self_assessment": assessment.model_dump(mode="json")}

    def _rule_checks(self, state: EvaluationState) -> EvaluationState:
        result = state["preparation"]
        expected_status = "completed" if self.finish_session else "stopped"
        recommendations = result.get("recommendations", [])
        resources = result.get("learning_resources", [])
        learning_levels = {"practice_only", "conceptual_only", "no_experience"}
        learning_skills = {
            item["skill"].casefold()
            for item in state["episodic_memory"]
            if item["experience_level"] in learning_levels
        }
        resource_topics_valid = all(
            str(item.get("topic", "")).casefold() in learning_skills for item in resources
        )
        checks = [
            RuleCheck(
                name="terminal_status",
                passed=result.get("status") == expected_status,
                detail=f"Expected {expected_status}, received {result.get('status')}.",
            ),
            RuleCheck(
                name="stopped_without_summary",
                passed=self.finish_session or not recommendations,
                detail="Stopped sessions must not generate recommendations.",
            ),
            RuleCheck(
                name="bounded_questions",
                passed=len(result.get("questions", [])) <= 5,
                detail=f"Generated {len(result.get('questions', []))} questions.",
            ),
            RuleCheck(
                name="bounded_resources",
                passed=len(resources) <= 6,
                detail=f"Returned {len(resources)} learning resources.",
            ),
            RuleCheck(
                name="resource_answer_alignment",
                passed=resource_topics_valid,
                detail="Learning resources must align with answers indicating a learning gap.",
            ),
        ]
        return {"rule_checks": [item.model_dump(mode="json") for item in checks]}


def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _json_prompt(payload: dict[str, object]) -> str:
    return "EVALUATION CONTEXT JSON:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
