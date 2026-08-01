from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.chat import (
    ChatCitation,
    ChatConversation,
    ChatDataScope,
    ChatRetrievalPlan,
    ChatSearchResultRef,
    ChatTurn,
)
from app.schemas.resume_profile import ResumeProfile
from app.services.chat_agent import (
    ChatAgentStep,
    ChatAgentToolCall,
    ChatAgentToolResult,
    classify_agent_failure,
    default_agent_tools,
    request_chat_agent_step,
)
from app.services.chat_agent_runtime import (
    ChatToolExecution,
    run_chat_agent,
)
from app.services.chat_context_builder import ChatEvidence, build_chat_evidence, evidence_packet
from app.services.chat_intent_rules import resolve_conversation_command
from app.services.chat_retrieval_planner import (
    build_agent_retrieval_plan,
    resolve_chat_retrieval,
)


class ProfileRepositoryStub:
    def __init__(self, profile: ResumeProfile) -> None:
        self.profile = profile

    def get(self, *, user_id: str, resume_profile_id: str):
        return (
            self.profile
            if user_id == self.profile.user_id
            and resume_profile_id == self.profile.resume_profile_id
            else None
        )

    def list_by_user(self, user_id: str):
        return [self.profile] if user_id == self.profile.user_id else []


class EmptyProfileRepository:
    def get(self, *, user_id: str, resume_profile_id: str):
        return None

    def list_by_user(self, user_id: str):
        return []


class EmptySearchRepository:
    def get(self, run_id: str, *, user_id: str):
        return None

    def list_recent_by_user(self, user_id: str, *, limit: int):
        return []


class EmptySavedJobRepository:
    def get(self, *, user_id: str, saved_job_id: str):
        return None

    def list_by_user(self, user_id: str):
        return []


class EmptyChatRepository:
    def list_turns(self, *, user_id: str, conversation_id: str, limit: int):
        return []


def _conversation(user_id: str = "user-1") -> ChatConversation:
    now = datetime.now(timezone.utc)
    return ChatConversation(
        conversation_id="conversation-1",
        user_id=user_id,
        title="Test",
        data_access_mode="auto",
        data_scope=ChatDataScope(),
        created_at=now,
        updated_at=now,
    )


def test_profile_context_excludes_raw_resume_text() -> None:
    now = datetime.now(timezone.utc)
    profile = ResumeProfile(
        resume_profile_id="profile-1",
        user_id="user-1",
        name="Primary profile",
        summary="Backend engineer",
        target_roles=["Backend Engineer"],
        core_skills=["Python"],
        raw_resume_text="TOP SECRET RAW RESUME TEXT",
        created_at=now,
        updated_at=now,
    )

    evidence, warnings = build_chat_evidence(
        "Give advice based on my profile",
        user_id="user-1",
        conversation=_conversation(),
        requested_sources=["profile"],
        profiles=ProfileRepositoryStub(profile),
        searches=EmptySearchRepository(),
        saved_jobs=EmptySavedJobRepository(),
        chats=EmptyChatRepository(),
    )

    assert warnings == []
    serialized = json.dumps(evidence_packet(evidence), ensure_ascii=False)
    assert "Backend engineer" in serialized
    assert "TOP SECRET RAW RESUME TEXT" not in serialized


def test_retry_command_resolves_latest_substantive_question() -> None:
    now = datetime.now(timezone.utc)
    prior = ChatTurn(
        turn_id="turn-1",
        conversation_id="conversation-1",
        user_id="user-1",
        sequence=1,
        client_turn_id="client-1",
        question="对比当前岗位和评分最高的 saved job",
        answer="Temporary fallback",
        status="completed",
        created_at=now,
        updated_at=now,
    )

    effective, command = resolve_conversation_command(
        "重试刚刚的问题",
        recent_turns=[prior],
    )

    assert effective == prior.question
    assert command == "retry_previous_question"


def test_retry_command_recognizes_composed_natural_language() -> None:
    now = datetime.now(timezone.utc)
    prior = ChatTurn(
        turn_id="turn-natural-retry",
        conversation_id="conversation-1",
        user_id="user-1",
        sequence=1,
        client_turn_id="client-natural-retry",
        question="对比 pinned JD 和最高分 saved job",
        answer="Temporary fallback",
        status="completed",
        created_at=now,
        updated_at=now,
    )

    effective, command = resolve_conversation_command(
        "重新尝试刚刚的问题",
        recent_turns=[prior],
    )

    assert effective == prior.question
    assert command == "retry_previous_question"


def test_agent_failure_categories_are_safe_and_actionable() -> None:
    assert classify_agent_failure(RuntimeError("request failed: connection refused")) == "network_error"
    assert classify_agent_failure(RuntimeError("HTTP 429 rate limit")) == "rate_limited"
    assert classify_agent_failure(RuntimeError("request timed out")) == "timeout"
    assert classify_agent_failure(ValueError("invalid JSON payload")) == "invalid_response"


def test_agent_step_accepts_structured_tool_query() -> None:
    class StructuredToolAgent:
        def chat_completion_json(self, *, system_prompt, user_prompt, expected_root_key=None):
            return {
                "action": "use_tools",
                "tool_calls": [{
                    "call_id": "python-jobs",
                    "name": "search_personal_knowledge",
                    "query": "saved jobs that explicitly require Python",
                }],
                "answer": "",
                "citation_ids": [],
                "limitations": [],
            }

    step, warning = request_chat_agent_step(
        "Which saved jobs require Python?",
        conversation=_conversation(),
        recent_turns=[],
        context_manifest={},
        evidence=[],
        llm_service=StructuredToolAgent(),
    )

    assert warning is None
    assert step is not None
    assert step.tool_calls == [ChatAgentToolCall(
        call_id="python-jobs",
        name="search_personal_knowledge",
        query="saved jobs that explicitly require Python",
    )]


def test_agent_runtime_can_refine_retrieval_after_tool_results() -> None:
    decisions: list[tuple[int, bool]] = []

    def decide(evidence, tool_results, require_final):
        decisions.append((len(tool_results), require_final))
        if not tool_results:
            return ChatAgentStep(
                action="use_tools",
                tool_calls=[ChatAgentToolCall(
                    call_id="call-python",
                    name="search_personal_knowledge",
                    query="saved jobs requiring Python",
                )],
                answer="",
                citation_ids=[],
                limitations=[],
            ), None
        if len(tool_results) == 1:
            return ChatAgentStep(
                action="use_tools",
                tool_calls=[ChatAgentToolCall(
                    call_id="call-fastapi",
                    name="search_personal_knowledge",
                    query="saved jobs requiring FastAPI",
                )],
                answer="",
                citation_ids=[],
                limitations=[],
            ), None
        return ChatAgentStep(
            action="final",
            tool_calls=[],
            answer="Two grounded roles were found.",
            citation_ids=["saved_job:call-python", "saved_job:call-fastapi"],
            limitations=[],
        ), None

    def execute(calls):
        call = calls[0]
        citation_id = f"saved_job:{call.call_id}"
        return ChatToolExecution(
            results=[ChatAgentToolResult(
                call_id=call.call_id,
                name=call.name,
                status="completed",
                citation_ids=[citation_id],
                warnings=[],
            )],
            evidence=[ChatEvidence(
                citation=ChatCitation(
                    citation_id=citation_id,
                    source_type="saved_jobs",
                    resource_id=call.call_id,
                    label=call.query or call.name,
                ),
                content={"query": call.query},
            )],
            retrieval_plan=ChatRetrievalPlan(
                agent_sources=["saved_jobs"],
                policy_reasons=["agent_tool:search_personal_knowledge"],
            ),
        )

    result = run_chat_agent(
        decide=decide,
        execute_tools=execute,
        policy_tools=[],
    )

    assert decisions == [(0, False), (1, False), (2, False)]
    assert result.final_step is not None
    assert len(result.evidence) == 2
    assert result.requested_tools == ["search_personal_knowledge"]


def test_agent_runtime_stops_repeated_identical_tool_call() -> None:
    decision_count = 0
    execution_count = 0

    def decide(evidence, tool_results, require_final):
        nonlocal decision_count
        decision_count += 1
        if require_final:
            return ChatAgentStep(
                action="final",
                tool_calls=[],
                answer="The available evidence is insufficient.",
                citation_ids=[],
                limitations=["No additional matches were found."],
            ), None
        return ChatAgentStep(
            action="use_tools",
            tool_calls=[ChatAgentToolCall(
                call_id=f"call-{decision_count}",
                name="search_personal_knowledge",
                query="same query",
            )],
            answer="",
            citation_ids=[],
            limitations=[],
        ), None

    def execute(calls):
        nonlocal execution_count
        execution_count += 1
        call = calls[0]
        return ChatToolExecution(
            results=[ChatAgentToolResult(
                call_id=call.call_id,
                name=call.name,
                status="completed",
                citation_ids=[],
                warnings=[],
            )],
            evidence=[],
            retrieval_plan=ChatRetrievalPlan(agent_sources=["saved_jobs"]),
        )

    result = run_chat_agent(
        decide=decide,
        execute_tools=execute,
        policy_tools=[],
    )

    assert execution_count == 1
    assert decision_count == 3
    assert result.final_step is not None
    assert result.final_step.action == "final"
    assert "agent_repeated_tool_call" in result.warnings


def test_agent_runtime_enforces_tool_round_limit() -> None:
    execution_count = 0

    def decide(evidence, tool_results, require_final):
        index = len(tool_results)
        return ChatAgentStep(
            action="use_tools",
            tool_calls=[ChatAgentToolCall(
                call_id=f"call-{index}",
                name="search_personal_knowledge",
                query=f"query {index}",
            )],
            answer="",
            citation_ids=[],
            limitations=[],
        ), None

    def execute(calls):
        nonlocal execution_count
        execution_count += 1
        call = calls[0]
        return ChatToolExecution(
            results=[ChatAgentToolResult(
                call_id=call.call_id,
                name=call.name,
                status="completed",
                citation_ids=[],
                warnings=[],
            )],
            evidence=[],
            retrieval_plan=ChatRetrievalPlan(agent_sources=["saved_jobs"]),
        )

    result = run_chat_agent(
        decide=decide,
        execute_tools=execute,
        policy_tools=[],
    )

    assert execution_count == 3
    assert result.final_step is None
    assert "agent_tool_round_limit" in result.warnings


def test_saved_job_highest_score_selector_is_deterministic() -> None:
    def job(job_id: str, score: int):
        return SimpleNamespace(
            saved_job_id=job_id,
            title=f"Role {job_id}",
            company="Example",
            location="Shenzhen",
            status="saved",
            tags=[],
            notes=None,
            raw_jd_text="Python agent development",
            latest_analysis=SimpleNamespace(
                match_score=score,
                recommendation="Review this role.",
                matched_strengths=[],
                critical_gaps=[],
            ),
        )

    class SavedJobs:
        def list_by_user(self, user_id: str):
            return [job("low", 45), job("high", 91), job("middle", 72)]

        def get(self, *, user_id: str, saved_job_id: str):
            return None

    evidence, warnings = build_chat_evidence(
        "对比当前岗位和 saved job 里评分最高的岗位",
        user_id="user-1",
        conversation=_conversation().model_copy(update={
            "data_scope": ChatDataScope(saved_job_ids=["low"]),
        }),
        requested_sources=["saved_jobs"],
        profiles=EmptyProfileRepository(),
        searches=EmptySearchRepository(),
        saved_jobs=SavedJobs(),
        chats=EmptyChatRepository(),
    )

    assert warnings == []
    assert [item.citation.resource_id for item in evidence] == ["high"]
    assert evidence[0].citation.excerpt.startswith("Match score: 91/100.")


def test_agent_plan_combines_previous_references_and_pinned_context() -> None:
    conversation = _conversation().model_copy(update={
        "data_scope": ChatDataScope(job_search_result_refs=[ChatSearchResultRef(
            job_search_run_id="run-1",
            job_result_id="result-1",
        )]),
    })
    previous = ChatTurn(
        turn_id="turn-1",
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        sequence=1,
        client_turn_id="client-1",
        question="Compare my saved jobs",
        answer="The first role is stronger.",
        status="completed",
        retrieval_used=True,
        retrieved_refs=["saved_job:saved-1", "profile:profile-1"],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )
    manifest = {
        "pinned_context": [{"source_type": "search_results", "label": "Pinned JD"}],
        "previous_references": [{"source_type": "saved_jobs", "label": "Saved role"}],
    }
    tools = default_agent_tools(
        "Compare these two jobs for me",
        conversation=conversation,
        context_manifest=manifest,
    )
    plan = build_agent_retrieval_plan(
        "Compare these two jobs for me",
        tool_calls=tools,
        conversation=conversation,
        recent_turns=[previous],
    )
    resolved = resolve_chat_retrieval(plan, recent_turns=[previous])

    assert tools == ["read_profile", "read_pinned_context", "read_previous_references"]
    assert [(item.source, item.strategy) for item in plan.requests] == [
        ("profile", "reuse_previous"),
        ("search_results", "use_pinned"),
        ("saved_jobs", "reuse_previous"),
    ]
    assert resolved.active_refs == ["saved_job:saved-1", "profile:profile-1"]


def test_agent_policy_uses_pinned_result_for_first_follow_up() -> None:
    conversation = _conversation().model_copy(update={
        "data_scope": ChatDataScope(job_search_result_refs=[ChatSearchResultRef(
            job_search_run_id="run-1",
            job_result_id="result-1",
        )]),
    })
    tools = default_agent_tools(
        "What about this job's main risks?",
        conversation=conversation,
        context_manifest={"pinned_context": [{"source_type": "search_results"}]},
    )
    plan = build_agent_retrieval_plan(
        "What about this job's main risks?",
        tool_calls=tools,
        conversation=conversation,
        recent_turns=[],
    )

    assert [(item.source, item.strategy) for item in plan.requests] == [
        ("search_results", "use_pinned")
    ]


def test_agent_policy_supplements_profile_for_fit_without_expanding_permissions() -> None:
    conversation = _conversation().model_copy(update={
        "data_scope": ChatDataScope(
            allowed_sources=["profile", "saved_jobs"],
            resume_profile_id="profile-1",
            saved_job_ids=["saved-1"],
        ),
    })
    tools = default_agent_tools(
        "Is this role suitable for me?",
        conversation=conversation,
        context_manifest={"pinned_context": [{"source_type": "saved_jobs"}]},
    )
    plan = build_agent_retrieval_plan(
        "Is this role suitable for me?",
        tool_calls=tools,
        conversation=conversation,
        recent_turns=[],
    )

    assert [item.source for item in plan.requests] == ["profile", "saved_jobs"]
    assert all(item.strategy == "use_pinned" for item in plan.requests)


def test_agent_policy_removes_tools_outside_allowlist() -> None:
    conversation = _conversation().model_copy(update={
        "data_scope": ChatDataScope(
            allowed_sources=["saved_jobs"],
            resume_profile_id="profile-1",
            saved_job_ids=["saved-1"],
        ),
    })
    tools = default_agent_tools(
        "Is this role suitable for me?",
        conversation=conversation,
        context_manifest={"pinned_context": [{"source_type": "saved_jobs"}]},
    )
    plan = build_agent_retrieval_plan(
        "Is this role suitable for me?",
        tool_calls=tools,
        conversation=conversation,
        recent_turns=[],
    )

    assert [item.source for item in plan.requests] == ["saved_jobs"]
    assert "disallowed_sources_removed" in plan.policy_reasons


def test_explicit_turn_attachment_has_priority_and_exact_reference() -> None:
    conversation = _conversation()
    plan = build_agent_retrieval_plan(
        "What are the main risks in this job?",
        tool_calls=[],
        conversation=conversation,
        recent_turns=[],
        attachment_sources=["search_results"],
    )
    resolved = resolve_chat_retrieval(
        plan,
        recent_turns=[],
        attachment_refs=["search_result:run-current:result-current"],
    )

    assert [(item.source, item.strategy) for item in plan.requests] == [
        ("search_results", "use_attachment")
    ]
    assert resolved.active_refs == ["search_result:run-current:result-current"]


def test_refresh_required_reuses_selector_but_not_cached_content() -> None:
    conversation = _conversation().model_copy(update={
        "last_retrieval_used": True,
        "last_retrieval_sources": ["search_results"],
        "data_scope": ChatDataScope(job_search_run_ids=["run-1"]),
    })
    previous = ChatTurn(
        turn_id="turn-refresh",
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        sequence=1,
        client_turn_id="client-refresh",
        question="Show this search result",
        answer="Prior answer",
        status="completed",
        retrieval_used=True,
        retrieved_refs=["search_result:run-1:result-1"],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )
    plan = build_agent_retrieval_plan(
        "Refresh the latest search results",
        tool_calls=["read_previous_references"],
        conversation=conversation,
        recent_turns=[previous],
    )
    resolved = resolve_chat_retrieval(plan, recent_turns=[previous])

    assert plan.freshness == "refresh_required"
    assert plan.requests[0].source == "search_results"
    assert plan.requests[0].strategy == "reuse_previous"
    assert resolved.active_refs == ["search_result:run-1:result-1"]


def test_data_access_off_overrides_agent_tools() -> None:
    conversation = _conversation().model_copy(update={"data_access_mode": "off"})
    plan = build_agent_retrieval_plan(
        "Compare my saved jobs",
        tool_calls=["find_saved_jobs"],
        conversation=conversation,
        recent_turns=[],
    )

    assert plan.requests == []
    assert plan.policy_reasons == ["data_access_off"]


def test_semantic_personal_question_selects_mcp_knowledge_tool() -> None:
    conversation = _conversation()

    tools = default_agent_tools(
        "我收藏过哪些要求 Kubernetes 的岗位？",
        conversation=conversation,
        context_manifest={},
    )
    plan = build_agent_retrieval_plan(
        "我收藏过哪些要求 Kubernetes 的岗位？",
        tool_calls=tools,
        conversation=conversation,
        recent_turns=[],
    )

    assert tools == ["search_personal_knowledge"]
    assert plan.agent_sources == ["saved_jobs"]
    assert plan.requests == []
    assert "agent_tool:search_personal_knowledge" in plan.policy_reasons


def test_personal_experience_question_targets_resume_knowledge() -> None:
    conversation = _conversation()

    tools = default_agent_tools(
        "我的哪些经历能够证明后端开发能力？",
        conversation=conversation,
        context_manifest={},
    )
    plan = build_agent_retrieval_plan(
        "我的哪些经历能够证明后端开发能力？",
        tool_calls=tools,
        conversation=conversation,
        recent_turns=[],
    )

    assert "search_personal_knowledge" in tools
    assert plan.agent_sources == ["profile"]


def test_search_context_combines_exact_results_with_whole_selected_runs() -> None:
    def search_result(result_id: str, title: str) -> SimpleNamespace:
        return SimpleNamespace(
            job_result_id=result_id,
            title=title,
            company="Example",
            location="Remote",
            description=f"{title} description",
            match_score=80,
            final_match_score=80,
            match_reasons=[],
            risks=[],
            evidence_quotes=[],
            unknowns=[],
            recommended_action=None,
            matched_keywords=[],
        )

    runs = {
        "run-exact": SimpleNamespace(
            job_search_run_id="run-exact",
            query="backend",
            status="completed",
            results=[search_result("keep", "Keep"), search_result("exclude", "Exclude")],
        ),
        "run-whole": SimpleNamespace(
            job_search_run_id="run-whole",
            query="platform",
            status="completed",
            results=[search_result("whole-a", "Whole A"), search_result("whole-b", "Whole B")],
        ),
    }

    class SearchRepositoryStub:
        def get(self, run_id: str, *, user_id: str):
            return runs.get(run_id) if user_id == "user-1" else None

        def list_recent_by_user(self, user_id: str, *, limit: int):
            return []

    conversation = _conversation().model_copy(update={
        "data_scope": ChatDataScope(
            job_search_run_ids=["run-whole"],
            job_search_result_refs=[ChatSearchResultRef(
                job_search_run_id="run-exact",
                job_result_id="keep",
            )],
        ),
    })

    evidence, warnings = build_chat_evidence(
        "Compare these roles",
        user_id="user-1",
        conversation=conversation,
        requested_sources=["search_results"],
        profiles=EmptyProfileRepository(),
        searches=SearchRepositoryStub(),
        saved_jobs=EmptySavedJobRepository(),
        chats=EmptyChatRepository(),
    )

    assert warnings == []
    assert {item.citation.resource_id for item in evidence} == {"keep", "whole-a", "whole-b"}
