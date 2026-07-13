from __future__ import annotations

import json
import re
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
from app.services.llm_observability import langfuse_agent_trace, langfuse_span
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
    evidence_memory: list[dict[str, object]]
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
        with langfuse_agent_trace("preparation-evaluation", metadata={
            "saved_job_id": saved_job_id,
            "profile_id": profile_id,
            "preparation_provider": self.preparation_provider,
            "evaluation_model": self.model.model_name,
        }):
            state = await self._graph.ainvoke({
                "user_id": user_id,
                "profile_id": profile_id,
                "saved_job_id": saved_job_id,
                "profile_memory": profile_memory,
                "evidence_memory": _build_evidence_memory(profile_memory),
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
        builder.add_edge(START, "start_preparation")
        builder.add_edge(["build_persona", "start_preparation"], "answer_question")
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
        builder.add_edge("finish_preparation", "rule_checks")
        builder.add_edge("rule_checks", "self_reflect")
        builder.add_edge("self_reflect", END)
        return builder.compile()

    def _build_persona(self, state: EvaluationState) -> EvaluationState:
        context = {
            "requested_archetype": self.persona_archetype,
            "profile_memory": state["profile_memory"],
            "evidence_memory": state["evidence_memory"],
            "job_context": state["job_context"],
        }
        response = self.model.generate_json(
            system_prompt=_prompt("persona_system.md"),
            user_prompt=_json_prompt(context),
            observation_name="evaluation.build_persona",
            observation_metadata={"stage": "persona_generation"},
            context_parts=context,
        )
        persona = CandidatePersona.model_validate(_normalize_persona_response(response))
        _validate_persona_memory(persona, state["evidence_memory"])
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
        candidate_context = _candidate_context(state, question)
        response = self.model.generate_json(
            system_prompt=_prompt("candidate_system.md"),
            user_prompt=_json_prompt(candidate_context),
            observation_name="evaluation.answer_question",
            observation_metadata={
                "stage": "candidate_answer",
                "question_id": question["question_id"],
                "question_index": index,
                "skill": question["skill"],
            },
            context_parts=candidate_context,
        )
        turn = CandidateTurn.model_validate({
            **response,
            "question_id": question["question_id"],
            "skill": question["skill"],
        })
        options = {item["option_id"]: item for item in question.get("options", [])}
        if turn.response_mode == "option":
            option = options.get(turn.selected_option_id or "") or next(
                (
                    item for item in options.values()
                    if item.get("value") == turn.experience_level
                ),
                None,
            )
            if option is None:
                raise ValueError(
                    f"Evaluation model selected an unavailable option: {turn.selected_option_id}"
                )
            turn = turn.model_copy(update={
                "selected_option_id": option["option_id"],
                "experience_level": option["value"],
            })
            answer = PreparationAnswer(
                question_id=turn.question_id,
                response_mode="option",
                selected_option_id=turn.selected_option_id,
                experience_level=turn.experience_level,
                detail=turn.detail,
            )
        else:
            if not question.get("free_text_allowed", True):
                raise ValueError("Evaluation model used free text when it was unavailable")
            answer = PreparationAnswer(
                question_id=turn.question_id,
                response_mode="free_text",
                free_text=turn.free_text,
            )
        _validate_turn_refs(
            [*turn.fact_refs, *(ref for claim in turn.claims for ref in claim.fact_refs)],
            state["evidence_memory"],
            state["persona_memory"],
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
        reflection_context = {
            "evidence_memory": state["evidence_memory"],
            "persona_memory": state["persona_memory"],
            "episodic_memory": _compact_episodic_memory(state["episodic_memory"]),
            "job_context": _compact_job_context(state["job_context"]),
            "preparation_result": _reflection_preparation_view(state["preparation"]),
            "deterministic_rule_checks": state["rule_checks"],
        }
        response = self.model.generate_json(
            system_prompt=_prompt("reflection_system.md"),
            user_prompt=_json_prompt(reflection_context),
            observation_name="evaluation.self_reflection",
            observation_metadata={"stage": "candidate_judge"},
            context_parts=reflection_context,
        )
        assessment = CandidateSelfAssessment.model_validate(response)
        return {"self_assessment": assessment.model_dump(mode="json")}

    def _rule_checks(self, state: EvaluationState) -> EvaluationState:
        result = state["preparation"]
        expected_status = "completed" if self.finish_session else "stopped"
        recommendations = result.get("recommendations", [])
        resources = result.get("learning_resources", [])
        learning_levels = {"practice_only", "conceptual_only", "no_experience"}
        question_by_id = {
            item["question_id"]: item for item in result.get("questions", [])
        }
        learning_skills = {
            question_by_id[item["question_id"]]["skill"].casefold()
            for item in result.get("answers", [])
            if item.get("experience_level") in learning_levels
            and item.get("question_id") in question_by_id
        }
        resource_topics_valid = all(
            str(item.get("topic", "")).casefold() in learning_skills for item in resources
        )
        gap_by_skill = {
            str(item.get("skill", "")).casefold(): item
            for item in result.get("skill_gaps", [])
        }
        required_learning_skills = {
            question_by_id[item["question_id"]]["skill"].casefold()
            for item in result.get("answers", [])
            if item.get("route") == "learning"
            and item.get("question_id") in question_by_id
            and gap_by_skill.get(
                str(question_by_id[item["question_id"]]["skill"]).casefold(), {}
            ).get("skill_type") == "knowledge"
        }
        covered_learning_skills = {
            str(item.get("topic", "")).casefold() for item in resources
        }
        missing_learning_resources = required_learning_skills - covered_learning_skills
        with langfuse_span(
            "evaluation.grounding_check",
            as_type="guardrail",
            metadata={"turn_count": len(state.get("episodic_memory", []))},
        ) as grounding_span:
            grounded, grounding_detail = _check_specific_fact_grounding(state)
            if grounding_span is not None:
                grounding_span.update(output={
                    "passed": grounded,
                    "detail": grounding_detail,
                })
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
            RuleCheck(
                name="required_learning_resources_present",
                passed=not missing_learning_resources,
                detail=(
                    "No answer routed to learning."
                    if not required_learning_skills
                    else (
                        f"Required={sorted(required_learning_skills)}; "
                        f"covered={sorted(covered_learning_skills)}; "
                        f"missing={sorted(missing_learning_resources)}."
                    )
                ),
            ),
            RuleCheck(
                name="specific_fact_grounding",
                passed=grounded,
                detail=grounding_detail,
            ),
        ]
        return {"rule_checks": [item.model_dump(mode="json") for item in checks]}


def _normalize_persona_response(response: dict[str, object]) -> dict[str, object]:
    normalized = {**response}
    calibrations = response.get("skill_calibrations")
    if not isinstance(calibrations, list):
        return normalized
    normalized["skill_calibrations"] = [
        {
            **item,
            "confidence": _normalize_confidence_label(item.get("confidence")),
        }
        if isinstance(item, dict)
        else item
        for item in calibrations
    ]
    return normalized


def _normalize_confidence_label(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = value.strip().casefold().replace("_", "-").replace(" ", "-")
    if cleaned in {"low", "medium", "high"}:
        return cleaned
    parts = {part for part in cleaned.split("-") if part}
    if "medium" in parts:
        return "medium"
    if "high" in parts:
        return "high"
    if "low" in parts:
        return "low"
    return value


def _build_evidence_memory(profile: dict[str, object]) -> list[dict[str, object]]:
    """Create stable references so later candidate turns can cite, not elaborate, facts."""
    memory: list[dict[str, object]] = []

    def visit(value: object, path: list[str]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key not in {
                    "resume_profile_id", "user_id", "source_session_id",
                    "source_confirmed_profile_id", "created_at", "updated_at",
                    "archived_at", "raw_resume_text",
                }:
                    visit(child, [*path, str(key)])
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, [*path, str(index)])
            return
        if value in (None, "", False):
            return
        field = ".".join(path)
        memory.append({
            "evidence_id": f"profile.{field}",
            "field": field,
            "content": value,
            "provenance": "resume_profile",
        })

    visit(profile, [])
    return memory


def _candidate_context(
    state: EvaluationState, question: dict[str, object]
) -> dict[str, object]:
    persona = state["persona_memory"]
    skill = str(question.get("skill") or "")
    calibrations = [
        item for item in persona.get("skill_calibrations", [])
        if isinstance(item, dict) and _skill_matches(skill, str(item.get("skill") or ""))
    ]
    referenced_ids = {
        str(ref)
        for item in calibrations
        for ref in [*item.get("evidence_refs", []), *item.get("scenario_fact_refs", [])]
    }
    skill_terms = _skill_terms(skill)
    scenarios = [
        item for item in persona.get("synthetic_scenario_memory", [])
        if isinstance(item, dict)
        and item.get("allowed_in_candidate_answer") is True
        and (
            str(item.get("fact_id")) in referenced_ids
            or skill_terms.intersection(_skill_terms(str(item.get("statement") or "")))
        )
    ]
    referenced_ids.update(
        str(ref) for item in scenarios for ref in item.get("evidence_refs", [])
    )
    evidence = [
        item for item in state["evidence_memory"]
        if str(item.get("evidence_id")) in referenced_ids
        or skill_terms.intersection(_skill_terms(str(item.get("content") or "")))
    ][:24]
    persona_view = {
        key: persona.get(key)
        for key in (
            "archetype", "confidence_style", "communication_style", "disclosure_style"
        )
    }
    persona_view.update({
        "skill_calibrations": [
            {
                key: item.get(key)
                for key in (
                    "skill", "actual_level", "confidence", "evidence_refs",
                    "scenario_fact_refs",
                )
            }
            for item in calibrations
        ],
        "synthetic_scenario_memory": scenarios,
        "memory_rule": "private_notes are intentionally unavailable; use only supplied fact IDs.",
    })
    return {
        "evidence_memory": evidence,
        "persona_memory": persona_view,
        "episodic_memory": _compact_episodic_memory(state.get("episodic_memory", [])),
        "job_context": _compact_job_context(state["job_context"]),
        "current_question": question,
    }


def _compact_episodic_memory(items: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = (
        "question_id", "skill", "response_mode", "selected_option_id",
        "experience_level", "detail", "free_text", "fact_refs",
        "claims",
    )
    return [{key: item.get(key) for key in keys} for item in items]


def _compact_job_context(job: dict[str, object]) -> dict[str, object]:
    return {
        key: job.get(key)
        for key in ("saved_job_id", "title", "company", "location")
    }


def _reflection_preparation_view(result: dict[str, object]) -> dict[str, object]:
    return {
        key: result.get(key)
        for key in (
            "status", "skill_gaps", "answers", "learning_resources",
            "recommendations", "question_generation", "recommendation_generation",
            "resource_mode", "resource_warning",
        )
    }


def _skill_matches(left: str, right: str) -> bool:
    left_terms = _skill_terms(left)
    right_terms = _skill_terms(right)
    if left_terms and right_terms and left_terms.intersection(right_terms):
        return True
    synonym_groups = (
        {"preprocessing", "cleaning", "annotation", "pipeline"},
        {"multimodal", "fusion"},
        {"deployment", "iteration", "mlops"},
    )
    return any(left_terms.intersection(group) and right_terms.intersection(group) for group in synonym_groups)


def _skill_terms(value: str) -> set[str]:
    ignored = {
        "and", "from", "with", "signal", "signals", "processing", "analysis",
        "design", "the", "for", "data",
    }
    return {
        item for item in re.findall(r"[a-z0-9]+", value.casefold())
        if len(item) > 2 and item not in ignored
    }


def _validate_memory_refs(
    refs: list[str], evidence_memory: list[dict[str, object]]
) -> None:
    allowed = {str(item["evidence_id"]) for item in evidence_memory}
    unknown = sorted(set(refs) - allowed)
    if unknown:
        raise ValueError(f"Evaluation model cited unknown evidence IDs: {unknown}")


def _validate_persona_memory(
    persona: CandidatePersona, evidence_memory: list[dict[str, object]]
) -> None:
    _validate_memory_refs(
        [ref for item in persona.skill_calibrations for ref in item.evidence_refs]
        + [ref for item in persona.synthetic_scenario_memory for ref in item.evidence_refs],
        evidence_memory,
    )
    fact_ids = [item.fact_id for item in persona.synthetic_scenario_memory]
    if len(fact_ids) != len(set(fact_ids)) or any(
        not item.startswith("scenario.") for item in fact_ids
    ):
        raise ValueError("Synthetic scenario fact IDs must be unique and start with scenario.")
    known = set(fact_ids)
    unknown = sorted({
        ref for item in persona.skill_calibrations for ref in item.scenario_fact_refs
        if ref not in known
    })
    if unknown:
        raise ValueError(f"Persona calibration cited unknown scenario facts: {unknown}")


def _validate_turn_refs(
    refs: list[str],
    evidence_memory: list[dict[str, object]],
    persona_memory: dict[str, object],
) -> None:
    evidence_ids = {str(item["evidence_id"]) for item in evidence_memory}
    scenario_items = persona_memory.get("synthetic_scenario_memory", [])
    scenario_ids = {
        str(item.get("fact_id"))
        for item in scenario_items
        if isinstance(item, dict) and item.get("allowed_in_candidate_answer") is True
    }
    unknown = sorted(set(refs) - evidence_ids - scenario_ids)
    if unknown:
        raise ValueError(f"Candidate cited unavailable or private fact IDs: {unknown}")


def _check_specific_fact_grounding(state: EvaluationState) -> tuple[bool, str]:
    evidence = {
        str(item["evidence_id"]): str(item.get("content") or "")
        for item in state["evidence_memory"]
    }
    scenario = {
        str(item.get("fact_id")): str(item.get("statement") or "")
        for item in state["persona_memory"].get("synthetic_scenario_memory", [])
        if isinstance(item, dict) and item.get("allowed_in_candidate_answer") is True
    }
    problems = []
    for turn in state.get("episodic_memory", []):
        text = str(turn.get("detail") or turn.get("free_text") or "")
        if not text:
            continue
        claims = turn.get("claims", [])
        if not claims:
            problems.append(f"{turn.get('skill')}: factual response has no structured claims")
            continue
        claim_terms: set[str] = set()
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_text = str(claim.get("claim") or "")
            refs = [str(item) for item in claim.get("fact_refs", [])]
            if not refs:
                problems.append(f"{turn.get('skill')}: claim has no fact_refs")
                continue
            support = " ".join(evidence.get(ref, scenario.get(ref, "")) for ref in refs)
            unsupported = _specific_terms(claim_text) - _specific_terms(support)
            if unsupported:
                problems.append(
                    f"{turn.get('skill')}: unsupported claim terms {sorted(unsupported)}"
                )
            claim_terms.update(_specific_terms(claim_text))
        uncovered = _specific_terms(text) - claim_terms
        if uncovered:
            problems.append(
                f"{turn.get('skill')}: response terms missing from claims {sorted(uncovered)}"
            )
    return (
        not problems,
        "All specific response terms are present in cited memories."
        if not problems else "; ".join(problems),
    )


def _specific_terms(text: str) -> set[str]:
    terms = re.findall(
        r"\b(?:[A-Z]{2,}(?:-[A-Z0-9]+)*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*|[A-Za-z]*\d+[A-Za-z0-9%.-]*)\b",
        text,
    )
    return {item.casefold() for item in terms if item.casefold() not in {"ai", "jd"}}


def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _json_prompt(payload: dict[str, object]) -> str:
    return "EVALUATION CONTEXT JSON:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
