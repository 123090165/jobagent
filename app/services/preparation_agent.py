from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.schemas.interview_preparation import PreparationAnswer, PreparationQuestion


class PreparationAgentState(TypedDict, total=False):
    preparation_id: str
    questions: list[dict[str, object]]
    answers: list[dict[str, object]]
    transitions: list[dict[str, object]]
    action: Literal["save", "complete", "stop"]
    status: Literal["questions_ready", "paused", "completed", "stopped"]


class PreparationAgent:
    """LangGraph boundary for the human-in-the-loop preparation session."""

    def start(self, preparation_id: str, questions: list[PreparationQuestion]) -> None:
        with self._graph() as graph:
            graph.invoke(
                {
                    "preparation_id": preparation_id,
                    "questions": [item.model_dump(mode="json") for item in questions],
                    "answers": [],
                    "transitions": [],
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


def _wait_for_user(state: PreparationAgentState) -> PreparationAgentState:
    response = interrupt({
        "preparation_id": state["preparation_id"],
        "questions": state.get("questions", []),
        "status": state.get("status", "questions_ready"),
    })
    return {
        "answers": response.get("answers", []),
        "action": response.get("action", "save"),
    }


def _route_action(state: PreparationAgentState) -> str:
    return state.get("action", "save")


def _reduce_answer_state(state: PreparationAgentState) -> PreparationAgentState:
    """Record validated semantic transitions without letting model text mutate graph state."""
    question_by_id = {
        str(item.get("question_id")): item for item in state.get("questions", [])
    }
    transitions = []
    for answer in state.get("answers", []):
        question_id = str(answer.get("question_id") or "")
        question = question_by_id.get(question_id, {})
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
        transitions.append({
            "question_id": question_id,
            "skill": question.get("skill"),
            "response_mode": answer.get("response_mode", "option"),
            "selected_option_id": answer.get("selected_option_id"),
            "evidence_transition": answer.get("evidence_transition") or option.get("evidence_transition"),
            "route": answer.get("route") or option.get("route") or "clarify",
        })
    return {"transitions": transitions}


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
    builder.add_node("reduce_answer_state", _reduce_answer_state)
    builder.add_node("pause", _pause)
    builder.add_node("complete", _complete)
    builder.add_node("stop", _stop)
    builder.add_edge(START, "wait_for_user")
    builder.add_edge("wait_for_user", "reduce_answer_state")
    builder.add_conditional_edges(
        "reduce_answer_state",
        _route_action,
        {"save": "pause", "complete": "complete", "stop": "stop"},
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
