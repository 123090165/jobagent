from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.schemas.interview_preparation import PreparationAnswer, PreparationQuestion


MAX_FOLLOW_UPS_PER_ANSWER = 1
_SPECIFIC_MARKERS = (
    "built", "created", "implemented", "used", "designed", "evaluated",
    "reduced", "increased", "result", "dataset", "method", "team",
    "实现", "使用", "负责", "设计", "评估", "优化", "结果", "数据集", "方法",
)


class PreparationAgentState(TypedDict, total=False):
    preparation_id: str
    questions: list[dict[str, object]]
    answers: list[dict[str, object]]
    transitions: list[dict[str, object]]
    pending_question_ids: list[str]
    answer_index: int
    action: Literal["save", "complete", "stop"]
    status: Literal["questions_ready", "paused", "completed", "stopped"]


class PreparationAgent:
    """Human-in-the-loop graph with backend-owned semantic transitions."""

    def start(self, preparation_id: str, questions: list[PreparationQuestion]) -> None:
        with self._graph() as graph:
            graph.invoke(
                {
                    "preparation_id": preparation_id,
                    "questions": [item.model_dump(mode="json") for item in questions],
                    "answers": [],
                    "transitions": [],
                    "pending_question_ids": [],
                    "answer_index": 0,
                    "status": "questions_ready",
                },
                self._config(preparation_id),
            )

    def resume(
        self,
        preparation_id: str,
        answers: list[PreparationAnswer],
        action: Literal["save", "complete", "stop"],
        *,
        questions: list[PreparationQuestion],
    ) -> PreparationAgentState:
        with self._graph() as graph:
            config = self._config(preparation_id)
            snapshot = graph.get_state(config)
            if not snapshot.values or not snapshot.next:
                graph.invoke(
                    {
                        "preparation_id": preparation_id,
                        "questions": [item.model_dump(mode="json") for item in questions],
                        "answers": [],
                        "transitions": [],
                        "pending_question_ids": [],
                        "answer_index": 0,
                        "status": "questions_ready",
                    },
                    config,
                )
            graph.invoke(
                Command(resume={
                    "answers": [item.model_dump(mode="json") for item in answers],
                    "action": action,
                }),
                config,
            )
            return PreparationAgentState(**graph.get_state(config).values)

    def _graph(self):
        return _compiled_graph(_checkpoint_path())

    @staticmethod
    def _config(preparation_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": preparation_id}}


def classify_answer_detail(answer: PreparationAnswer | dict[str, object]) -> str:
    if isinstance(answer, PreparationAnswer):
        detail = answer.detail or answer.free_text or answer.answer or ""
    else:
        detail = str(
            answer.get("detail") or answer.get("free_text") or answer.get("answer") or ""
        )
    detail = detail.strip()
    if not detail:
        return "not_provided"
    normalized = detail.casefold()
    has_marker = any(marker in normalized for marker in _SPECIFIC_MARKERS)
    enough_context = len(detail) >= 24 or any(character.isdigit() for character in detail)
    return "specific" if has_marker and enough_context else "vague"


def _wait_for_user(state: PreparationAgentState) -> PreparationAgentState:
    response = interrupt({
        "preparation_id": state["preparation_id"],
        "questions": state.get("questions", []),
        "status": state.get("status", "questions_ready"),
        "pending_question_ids": state.get("pending_question_ids", []),
    })
    return {
        "answers": response.get("answers", []),
        "action": response.get("action", "save"),
    }


def _normalize_answers(state: PreparationAgentState) -> PreparationAgentState:
    question_by_id = {
        str(item.get("question_id")): item for item in state.get("questions", [])
    }
    normalized_answers: list[dict[str, object]] = []
    for raw_answer in state.get("answers", []):
        answer = dict(raw_answer)
        question = question_by_id.get(str(answer.get("question_id") or ""), {})
        options = {
            str(item.get("option_id")): item for item in question.get("options", [])
        }
        option = options.get(str(answer.get("selected_option_id") or "")) or next(
            (
                item for item in options.values()
                if item.get("value") == answer.get("experience_level")
            ),
            {},
        )
        detail_quality = classify_answer_detail(answer)
        input_mode = (
            "free_text"
            if answer.get("response_mode") == "free_text"
            else "option_with_detail"
            if answer.get("detail")
            else "option_only"
        )
        level = answer.get("experience_level") or option.get("value")
        follow_up_count = int(answer.get("follow_up_count") or 0)
        route = answer.get("route") or option.get("route") or "clarify"
        evidence = (
            answer.get("evidence_transition")
            or option.get("evidence_transition")
            or "unknown"
        )
        pending_prompt: str | None = None

        if level in {"work_experience", "project_experience"}:
            if detail_quality == "specific":
                route, evidence = "next_skill", "supported"
            elif follow_up_count >= MAX_FOLLOW_UPS_PER_ANSWER:
                route, evidence = "next_skill", "partial"
            else:
                route, evidence = "ask_evidence", "partial"
                pending_prompt = str(
                    option.get("follow_up_prompt")
                    or "Describe your personal contribution, method, and how the result was evaluated."
                )
        elif level in {"practice_only", "conceptual_only"}:
            route, evidence = "learning", "partial"
        elif level == "no_experience":
            route, evidence = "capability_gap", "missing"
        elif level == "uncertain" or not level:
            if follow_up_count >= MAX_FOLLOW_UPS_PER_ANSWER:
                route, evidence = "next_skill", "unknown"
            else:
                route, evidence = "clarify", "unknown"
                pending_prompt = str(
                    option.get("follow_up_prompt")
                    or question.get("free_text_prompt")
                    or "Explain which boundary the available choices do not capture."
                )

        answer.update({
            "input_mode": input_mode,
            "experience_level": level,
            "detail_quality": detail_quality,
            "evidence_transition": evidence,
            "route": route,
            "pending_prompt": pending_prompt,
        })
        normalized_answers.append(answer)
    return {
        "answers": normalized_answers,
        "transitions": [],
        "pending_question_ids": [],
        "answer_index": 0,
    }


def _route_next_answer(state: PreparationAgentState) -> str:
    index = state.get("answer_index", 0)
    answers = state.get("answers", [])
    if index >= len(answers):
        return "finish"
    route = str(answers[index].get("route") or "clarify")
    if route not in {"ask_evidence", "learning", "capability_gap", "clarify", "next_skill"}:
        return "clarify"
    return route


def _record_current_route(
    state: PreparationAgentState,
    *,
    pending: bool,
) -> PreparationAgentState:
    index = state.get("answer_index", 0)
    answers = [dict(item) for item in state.get("answers", [])]
    answer = answers[index]
    question_by_id = {
        str(item.get("question_id")): item for item in state.get("questions", [])
    }
    question_id = str(answer.get("question_id") or "")
    question = question_by_id.get(question_id, {})
    pending_ids = list(state.get("pending_question_ids", []))
    is_completion_attempt = state.get("action") == "complete"
    if pending and is_completion_attempt:
        answer["follow_up_count"] = min(
            int(answer.get("follow_up_count") or 0) + 1,
            MAX_FOLLOW_UPS_PER_ANSWER,
        )
        if question_id and question_id not in pending_ids:
            pending_ids.append(question_id)
    answers[index] = answer
    transitions = list(state.get("transitions", []))
    transitions.append({
        "question_id": question_id,
        "skill": question.get("skill"),
        "input_mode": answer.get("input_mode"),
        "response_mode": answer.get("response_mode", "option"),
        "selected_option_id": answer.get("selected_option_id"),
        "detail_quality": answer.get("detail_quality"),
        "evidence_transition": answer.get("evidence_transition"),
        "route": answer.get("route"),
        "pending": pending and is_completion_attempt,
        "follow_up_count": answer.get("follow_up_count", 0),
    })
    return {
        "answers": answers,
        "transitions": transitions,
        "pending_question_ids": pending_ids,
    }


def _ask_evidence(state: PreparationAgentState) -> PreparationAgentState:
    return _record_current_route(state, pending=True)


def _learning(state: PreparationAgentState) -> PreparationAgentState:
    return _record_current_route(state, pending=False)


def _capability_gap(state: PreparationAgentState) -> PreparationAgentState:
    return _record_current_route(state, pending=False)


def _clarify(state: PreparationAgentState) -> PreparationAgentState:
    return _record_current_route(state, pending=True)


def _next_skill(state: PreparationAgentState) -> PreparationAgentState:
    return _record_current_route(state, pending=False)


def _advance_answer(state: PreparationAgentState) -> PreparationAgentState:
    return {"answer_index": state.get("answer_index", 0) + 1}


def _finish_answers(_: PreparationAgentState) -> PreparationAgentState:
    return {}


def _route_session_action(state: PreparationAgentState) -> str:
    action = state.get("action", "save")
    if action == "stop":
        return "stop"
    if action == "save" or state.get("pending_question_ids"):
        return "pause"
    return "complete"


def _pause(state: PreparationAgentState) -> PreparationAgentState:
    return {"status": "paused"}


def _complete(state: PreparationAgentState) -> PreparationAgentState:
    return {"status": "completed"}


def _stop(state: PreparationAgentState) -> PreparationAgentState:
    return {"status": "stopped"}


def _compiled_graph(path: str):
    saver_context = SqliteSaver.from_conn_string(path)
    saver = saver_context.__enter__()
    saver.setup()
    builder = StateGraph(PreparationAgentState)
    builder.add_node("wait_for_user", _wait_for_user)
    builder.add_node("normalize_answers", _normalize_answers)
    builder.add_node("ask_evidence", _ask_evidence)
    builder.add_node("learning", _learning)
    builder.add_node("capability_gap", _capability_gap)
    builder.add_node("clarify", _clarify)
    builder.add_node("next_skill", _next_skill)
    builder.add_node("advance_answer", _advance_answer)
    builder.add_node("finish_answers", _finish_answers)
    builder.add_node("pause", _pause)
    builder.add_node("complete", _complete)
    builder.add_node("stop", _stop)
    builder.add_edge(START, "wait_for_user")
    builder.add_edge("wait_for_user", "normalize_answers")
    route_map = {
        "ask_evidence": "ask_evidence",
        "learning": "learning",
        "capability_gap": "capability_gap",
        "clarify": "clarify",
        "next_skill": "next_skill",
        "finish": "finish_answers",
    }
    builder.add_conditional_edges("normalize_answers", _route_next_answer, route_map)
    for node in ("ask_evidence", "learning", "capability_gap", "clarify", "next_skill"):
        builder.add_edge(node, "advance_answer")
    builder.add_conditional_edges("advance_answer", _route_next_answer, route_map)
    builder.add_conditional_edges(
        "finish_answers",
        _route_session_action,
        {"pause": "pause", "complete": "complete", "stop": "stop"},
    )
    builder.add_edge("pause", "wait_for_user")
    builder.add_edge("complete", END)
    builder.add_edge("stop", END)
    graph = builder.compile(checkpointer=saver)

    class GraphContext:
        def __enter__(self):
            return graph

        def __exit__(self, exc_type, exc, traceback):
            saver_context.__exit__(exc_type, exc, traceback)

    return GraphContext()


def _checkpoint_path() -> str:
    configured = os.getenv("JOBAGENT_LANGGRAPH_DB_PATH", "").strip()
    if configured:
        path = Path(configured)
    else:
        app_db = Path(os.getenv("JOBAGENT_DB_PATH", "data/jobagent.sqlite3"))
        path = app_db.with_name(f"{app_db.stem}.langgraph.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


preparation_agent = PreparationAgent()
