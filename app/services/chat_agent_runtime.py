from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.chat import ChatRetrievalPlan
from app.services.chat_agent import (
    ChatAgentStep,
    ChatAgentToolCall,
    ChatAgentToolName,
    ChatAgentToolResult,
)
from app.services.chat_context_builder import ChatEvidence


MAX_TOOL_ROUNDS = 3


@dataclass(frozen=True)
class ChatToolExecution:
    results: list[ChatAgentToolResult]
    evidence: list[ChatEvidence]
    retrieval_plan: ChatRetrievalPlan


@dataclass(frozen=True)
class ChatAgentRun:
    final_step: ChatAgentStep | None
    evidence: list[ChatEvidence]
    retrieval_plan: ChatRetrievalPlan
    requested_tools: list[ChatAgentToolName]
    warnings: list[str]


class ChatAgentRuntimeState(TypedDict, total=False):
    final_step: ChatAgentStep | None
    pending_calls: list[ChatAgentToolCall]
    tool_results: list[ChatAgentToolResult]
    evidence: list[ChatEvidence]
    retrieval_plan: ChatRetrievalPlan
    requested_tools: list[ChatAgentToolName]
    executed_signatures: list[str]
    warnings: list[str]
    tool_rounds: int
    finished: bool


DecisionFunction = Callable[
    [list[ChatEvidence], list[ChatAgentToolResult], bool],
    tuple[ChatAgentStep | None, str | None],
]
ToolExecutor = Callable[[list[ChatAgentToolCall]], ChatToolExecution]


def run_chat_agent(
    *,
    decide: DecisionFunction,
    execute_tools: ToolExecutor,
    policy_tools: list[ChatAgentToolName],
) -> ChatAgentRun:
    """Run one bounded Pi-style tool loop on a small LangGraph state machine."""

    def decide_node(state: ChatAgentRuntimeState) -> ChatAgentRuntimeState:
        force_final = state.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS
        step, warning = decide(
            state.get("evidence", []),
            state.get("tool_results", []),
            force_final,
        )
        warnings = _append_warning(state.get("warnings", []), warning)
        calls = list(step.tool_calls) if step is not None and step.action == "use_tools" else []
        if state.get("tool_rounds", 0) == 0:
            calls = _merge_policy_calls(policy_tools, calls)

        executed = set(state.get("executed_signatures", []))
        fresh_calls = [
            item for item in calls
            if _tool_signature(item) not in executed
        ]
        if len(fresh_calls) != len(calls):
            warnings = _append_warning(warnings, "agent_repeated_tool_call")
        calls = fresh_calls

        if force_final and calls:
            warnings = _append_warning(warnings, "agent_tool_round_limit")
            step = None
            calls = []
        elif not calls and step is not None and step.action == "use_tools":
            step, warning = decide(
                state.get("evidence", []),
                state.get("tool_results", []),
                True,
            )
            warnings = _append_warning(warnings, warning)

        if step is not None and step.action == "final" and not calls:
            return {
                **state,
                "final_step": step,
                "pending_calls": [],
                "warnings": warnings,
                "finished": True,
            }
        if not calls:
            return {
                **state,
                "final_step": None,
                "pending_calls": [],
                "warnings": warnings,
                "finished": True,
            }
        return {
            **state,
            "pending_calls": calls,
            "warnings": warnings,
            "finished": False,
        }

    def tool_node(state: ChatAgentRuntimeState) -> ChatAgentRuntimeState:
        calls = state.get("pending_calls", [])
        execution = execute_tools(calls)
        evidence = _merge_evidence(state.get("evidence", []), execution.evidence)
        plan = _merge_retrieval_plans(
            state.get("retrieval_plan", ChatRetrievalPlan()),
            execution.retrieval_plan,
        )
        return {
            **state,
            "pending_calls": [],
            "tool_results": [*state.get("tool_results", []), *execution.results],
            "evidence": evidence,
            "retrieval_plan": plan,
            "requested_tools": list(dict.fromkeys([
                *state.get("requested_tools", []),
                *(item.name for item in calls),
            ])),
            "executed_signatures": list(dict.fromkeys([
                *state.get("executed_signatures", []),
                *(_tool_signature(item) for item in calls),
            ])),
            "warnings": list(dict.fromkeys([
                *state.get("warnings", []),
                *(warning for item in execution.results for warning in item.warnings),
            ])),
            "tool_rounds": state.get("tool_rounds", 0) + 1,
        }

    graph = StateGraph(ChatAgentRuntimeState)
    graph.add_node("decide", decide_node)
    graph.add_node("execute_tools", tool_node)
    graph.add_edge(START, "decide")
    graph.add_conditional_edges(
        "decide",
        lambda state: "finish" if state.get("finished") else "execute_tools",
        {"finish": END, "execute_tools": "execute_tools"},
    )
    graph.add_edge("execute_tools", "decide")
    completed = graph.compile().invoke({
        "final_step": None,
        "pending_calls": [],
        "tool_results": [],
        "evidence": [],
        "retrieval_plan": ChatRetrievalPlan(),
        "requested_tools": [],
        "executed_signatures": [],
        "warnings": [],
        "tool_rounds": 0,
        "finished": False,
    })
    return ChatAgentRun(
        final_step=completed.get("final_step"),
        evidence=completed.get("evidence", []),
        retrieval_plan=completed.get("retrieval_plan", ChatRetrievalPlan()),
        requested_tools=completed.get("requested_tools", []),
        warnings=completed.get("warnings", []),
    )


def _merge_policy_calls(
    policy_tools: list[ChatAgentToolName],
    model_calls: list[ChatAgentToolCall],
) -> list[ChatAgentToolCall]:
    calls = list(model_calls)
    existing = {item.name for item in calls}
    calls.extend(
        ChatAgentToolCall(call_id=f"policy:{name}", name=name)
        for name in policy_tools
        if name not in existing
    )
    return calls


def _tool_signature(call: ChatAgentToolCall) -> str:
    return f"{call.name}:{(call.query or '').casefold().strip()}"


def _merge_evidence(
    existing: list[ChatEvidence],
    incoming: list[ChatEvidence],
) -> list[ChatEvidence]:
    by_id = {item.citation.citation_id: item for item in [*existing, *incoming]}
    return list(by_id.values())


def _merge_retrieval_plans(
    existing: ChatRetrievalPlan,
    incoming: ChatRetrievalPlan,
) -> ChatRetrievalPlan:
    requests = {
        item.source: item
        for item in [*existing.requests, *incoming.requests]
    }
    return ChatRetrievalPlan(
        agent_sources=list(dict.fromkeys([
            *existing.agent_sources,
            *incoming.agent_sources,
        ])),
        requests=list(requests.values()),
        freshness=(
            "refresh_required"
            if "refresh_required" in {existing.freshness, incoming.freshness}
            else "reuse_allowed"
        ),
        policy_reasons=list(dict.fromkeys([
            *existing.policy_reasons,
            *incoming.policy_reasons,
        ]))[:8],
    )


def _append_warning(values: list[str], warning: str | None) -> list[str]:
    return list(dict.fromkeys([*values, *([warning] if warning else [])]))
