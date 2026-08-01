from __future__ import annotations

from dataclasses import dataclass

from app.schemas.chat import (
    ChatConversation,
    ChatRetrievalPlan,
    ChatRetrievalRequest,
    ChatRetrievalStrategy,
    ChatSource,
    ChatTurn,
)
from app.services.chat_agent import ChatAgentToolName, personal_knowledge_sources
from app.services.chat_intent_rules import (
    requests_highest_saved_job_score,
    requires_fresh_context,
)


_REF_PREFIXES: dict[ChatSource, str] = {
    "profile": "profile:",
    "search_results": "search_result:",
    "saved_jobs": "saved_job:",
    "chat_history": "chat_turn:",
}


@dataclass(frozen=True)
class ResolvedChatRetrieval:
    sources: list[ChatSource]
    active_refs: list[str]


def build_agent_retrieval_plan(
    question: str,
    *,
    tool_calls: list[ChatAgentToolName],
    conversation: ChatConversation,
    recent_turns: list[ChatTurn],
    attachment_sources: list[ChatSource] | None = None,
) -> ChatRetrievalPlan:
    attachment_sources = list(dict.fromkeys(attachment_sources or []))
    freshness = "refresh_required" if requires_fresh_context(question) else "reuse_allowed"
    if conversation.data_access_mode == "off":
        return ChatRetrievalPlan(
            freshness=freshness,
            policy_reasons=["data_access_off"],
        )

    pinned_sources = _pinned_sources(conversation)
    previous_sources = _previous_sources(recent_turns)
    requests_by_source: dict[ChatSource, ChatRetrievalRequest] = {}
    semantic_sources: list[ChatSource] = []

    def add(source: ChatSource, strategy: ChatRetrievalStrategy, reason: str) -> None:
        existing = requests_by_source.get(source)
        priorities = {"load_recent": 0, "use_pinned": 1, "reuse_previous": 2, "use_attachment": 3}
        if existing is None or priorities[strategy] > priorities[existing.strategy]:
            requests_by_source[source] = ChatRetrievalRequest(
                source=source,
                strategy=strategy,
                policy_reason=reason,
            )

    for source in attachment_sources:
        add(source, "use_attachment", "explicit_attachment")
    for tool_name in tool_calls:
        if tool_name == "read_profile":
            add("profile", "use_pinned" if "profile" in pinned_sources else "load_recent", "agent_tool:read_profile")
        elif tool_name == "read_pinned_context":
            for source in pinned_sources:
                add(source, "use_pinned", "agent_tool:read_pinned_context")
        elif tool_name == "read_previous_references":
            for source in previous_sources:
                add(source, "reuse_previous", "agent_tool:read_previous_references")
        elif tool_name == "find_saved_jobs":
            add(
                "saved_jobs",
                (
                    "use_pinned"
                    if (
                        "saved_jobs" in pinned_sources
                        and not requests_highest_saved_job_score(question)
                    )
                    else "load_recent"
                ),
                "agent_tool:find_saved_jobs",
            )
        elif tool_name == "search_personal_knowledge":
            semantic_sources.extend(
                personal_knowledge_sources(
                    question,
                    allowed_sources=conversation.data_scope.allowed_sources,
                )
            )
        elif tool_name == "read_search_results":
            add(
                "search_results",
                "use_pinned" if "search_results" in pinned_sources else "load_recent",
                "agent_tool:read_search_results",
            )
        elif tool_name == "read_chat_history":
            add("chat_history", "load_recent", "agent_tool:read_chat_history")

    allowed = set(conversation.data_scope.allowed_sources)
    requests = [request for source, request in requests_by_source.items() if source in allowed]
    policy_reasons = ["agent_tool_selection"] if tool_calls else []
    if attachment_sources:
        policy_reasons.append("explicit_attachment")
    if semantic_sources:
        policy_reasons.append("agent_tool:search_personal_knowledge")
    if len(requests) != len(requests_by_source):
        policy_reasons.append("disallowed_sources_removed")
    return ChatRetrievalPlan(
        agent_sources=list(dict.fromkeys([
            *(request.source for request in requests),
            *semantic_sources,
        ])),
        requests=requests,
        freshness=freshness,
        policy_reasons=policy_reasons,
    )


def resolve_chat_retrieval(
    plan: ChatRetrievalPlan,
    *,
    recent_turns: list[ChatTurn],
    attachment_refs: list[str] | None = None,
) -> ResolvedChatRetrieval:
    attachment_refs = attachment_refs or []
    attachment_sources = {
        request.source for request in plan.requests
        if request.strategy == "use_attachment"
    }
    reuse_sources = {
        request.source for request in plan.requests
        if request.strategy == "reuse_previous"
    }
    active_refs = [
        ref for ref in attachment_refs
        if any(ref.startswith(_REF_PREFIXES[source]) for source in attachment_sources)
    ]
    if reuse_sources:
        previous = next(
            (
                turn for turn in reversed(recent_turns)
                if turn.status == "completed" and turn.retrieval_used
            ),
            None,
        )
        if previous is not None:
            active_refs.extend(
                ref for ref in previous.retrieved_refs
                if any(
                    ref.startswith(_REF_PREFIXES[source])
                    for source in reuse_sources
                )
            )
    return ResolvedChatRetrieval(
        sources=[request.source for request in plan.requests],
        active_refs=list(dict.fromkeys(active_refs)),
    )


def _pinned_sources(conversation: ChatConversation) -> list[ChatSource]:
    scope = conversation.data_scope
    sources: list[ChatSource] = []
    if scope.resume_profile_id:
        sources.append("profile")
    if scope.job_search_run_ids or scope.job_search_result_refs:
        sources.append("search_results")
    if scope.saved_job_ids:
        sources.append("saved_jobs")
    return sources


def _previous_sources(recent_turns: list[ChatTurn]) -> list[ChatSource]:
    previous = next(
        (turn for turn in reversed(recent_turns) if turn.status == "completed" and turn.retrieval_used),
        None,
    )
    if previous is None:
        return []
    sources: list[ChatSource] = []
    for ref in previous.retrieved_refs:
        for source, prefix in _REF_PREFIXES.items():
            if ref.startswith(prefix) and source not in sources:
                sources.append(source)
    return sources
