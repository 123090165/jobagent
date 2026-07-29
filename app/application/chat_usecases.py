from __future__ import annotations

from collections.abc import Sequence

from app.repositories.chat_repository import ChatRepository, chat_repository
from app.repositories.browser_job_capture_repository import (
    BrowserJobCaptureRepository,
    browser_job_capture_repository,
)
from app.repositories.job_search_repository import JobSearchRepository, job_search_repository
from app.repositories.resume_profile_repository import ResumeProfileRepository, resume_profile_repository
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.schemas.chat import (
    ChatBrowserCaptureAttachment,
    ChatConversation,
    ChatConversationCreateRequest,
    ChatConversationUpdateRequest,
    ChatContextCatalog,
    ChatDataScope,
    ChatMemoryResource,
    ChatMemoryStatus,
    ChatProfileContextOption,
    ChatSavedJobContextOption,
    ChatSavedJobAttachment,
    ChatSearchRunContextOption,
    ChatContextAttachment,
    ChatSearchResultRef,
    ChatSource,
    ChatTurn,
    ChatTurnCreateRequest,
)
from app.services.chat_agent import (
    citations_for_agent_step,
    default_agent_tools,
    derive_agent_route,
    hard_refusal_route,
    request_chat_agent_step,
)
from app.services.chat_answer_generator import (
    HARD_REFUSAL_ANSWER,
    compress_chat_memory,
    deterministic_chat_answer,
)
from app.services.chat_intent_rules import resolve_conversation_command
from app.services.chat_personal_knowledge import (
    build_chat_evidence_with_personal_knowledge,
)
from app.services.chat_retrieval_planner import (
    build_agent_retrieval_plan,
    resolve_chat_retrieval,
)
from app.services.errors import JobAgentError
from app.services.llm_observability import langfuse_agent_trace, llm_observation_context
from app.services.llm_provider import resolve_llm_provider


def create_chat_conversation(
    payload: ChatConversationCreateRequest,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> ChatConversation:
    _validate_data_scope(payload.data_scope, user_id=user_id)
    return repository.create_conversation(user_id=user_id, payload=payload)


def list_chat_conversations(
    *, user_id: str, limit: int = 50, repository: ChatRepository = chat_repository
) -> list[ChatConversation]:
    return repository.list_conversations(user_id=user_id, limit=limit)


def get_chat_context_catalog(
    *,
    user_id: str,
    profiles: ResumeProfileRepository = resume_profile_repository,
    searches: JobSearchRepository = job_search_repository,
    saved_jobs: SavedJobRepository = saved_job_repository,
) -> ChatContextCatalog:
    profile_items = profiles.list_by_user(user_id)
    search_items = searches.list_recent_by_user(user_id, limit=20)
    saved_items = saved_jobs.list_by_user(user_id)[:50]
    return ChatContextCatalog(
        profiles=[ChatProfileContextOption(
            resume_profile_id=item.resume_profile_id,
            label=item.name,
            summary=item.summary,
            is_default=item.is_default,
        ) for item in profile_items],
        search_runs=[ChatSearchRunContextOption(
            job_search_run_id=item.job_search_run_id,
            label=_search_run_label(item.query, len(item.results)),
            query=item.query,
            result_count=len(item.results),
            created_at=item.created_at,
        ) for item in search_items if item.status == "completed"],
        saved_jobs=[ChatSavedJobContextOption(
            saved_job_id=item.saved_job_id,
            label=f"{item.title} · {item.company or 'Unknown company'}",
            title=item.title,
            company=item.company,
            status=item.status,
            updated_at=item.updated_at,
        ) for item in saved_items],
    )


def get_chat_memory_status(
    conversation_id: str,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
    profiles: ResumeProfileRepository = resume_profile_repository,
    searches: JobSearchRepository = job_search_repository,
    saved_jobs: SavedJobRepository = saved_job_repository,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> ChatMemoryStatus:
    conversation = get_chat_conversation(
        conversation_id,
        user_id=user_id,
        repository=repository,
    )
    pinned_context = _resolve_pinned_memory_resources(
        conversation.data_scope,
        user_id=user_id,
        profiles=profiles,
        searches=searches,
        saved_jobs=saved_jobs,
        captures=captures,
    )
    latest_turn = repository.get_latest_completed_turn(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    previous_references = [
        ChatMemoryResource(
            source_type=citation.source_type,
            resource_id=citation.resource_id,
            label=citation.label,
            status="available" if _citation_is_available(
                citation.citation_id,
                source_type=citation.source_type,
                resource_id=citation.resource_id,
                user_id=user_id,
                conversation_id=conversation_id,
                repository=repository,
                profiles=profiles,
                searches=searches,
                saved_jobs=saved_jobs,
                captures=captures,
            ) else "unavailable",
        )
        for citation in (latest_turn.citations if latest_turn is not None else [])
    ]
    return ChatMemoryStatus(
        conversation_id=conversation_id,
        total_turn_count=repository.count_completed_turns(
            user_id=user_id,
            conversation_id=conversation_id,
        ),
        recent_turn_count=repository.count_completed_turns(
            user_id=user_id,
            conversation_id=conversation_id,
            after_sequence=conversation.summary_through_sequence,
        ),
        summary=conversation.summary,
        summary_version=conversation.summary_version,
        summary_through_sequence=conversation.summary_through_sequence,
        pinned_context=pinned_context,
        previous_references=previous_references,
        updated_at=conversation.updated_at,
    )


def get_chat_conversation(
    conversation_id: str,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> ChatConversation:
    conversation = repository.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if conversation is None:
        raise _not_found()
    return conversation


def update_chat_conversation(
    conversation_id: str,
    payload: ChatConversationUpdateRequest,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> ChatConversation:
    if payload.data_scope is not None:
        _validate_data_scope(payload.data_scope, user_id=user_id)
    conversation = repository.update_conversation(
        user_id=user_id, conversation_id=conversation_id, payload=payload
    )
    if conversation is None:
        raise _not_found()
    return conversation


def list_chat_turns(
    conversation_id: str,
    *,
    user_id: str,
    limit: int = 50,
    before_sequence: int | None = None,
    repository: ChatRepository = chat_repository,
) -> list[ChatTurn]:
    get_chat_conversation(conversation_id, user_id=user_id, repository=repository)
    return repository.list_turns(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
        before_sequence=before_sequence,
    )


def create_chat_turn(
    conversation_id: str,
    payload: ChatTurnCreateRequest,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> ChatTurn:
    conversation = get_chat_conversation(conversation_id, user_id=user_id, repository=repository)
    retry_source = None
    if payload.retry_of_turn_id:
        retry_source = repository.get_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=payload.retry_of_turn_id,
        )
        if retry_source is None:
            raise _not_found()
    turn_question = retry_source.question if retry_source is not None else payload.question
    effective_attachments = (
        retry_source.context_attachments
        if retry_source is not None
        else payload.context_attachments
    )
    search_attachments = [
        item for item in effective_attachments
        if isinstance(item, ChatContextAttachment)
    ]
    saved_job_attachments = [
        item for item in effective_attachments
        if isinstance(item, ChatSavedJobAttachment)
    ]
    capture_attachments = [
        item for item in effective_attachments
        if isinstance(item, ChatBrowserCaptureAttachment)
    ]
    _validate_search_result_refs(
        search_attachments,
        user_id=user_id,
    )
    _validate_saved_job_ids(
        [item.saved_job_id for item in saved_job_attachments],
        user_id=user_id,
    )
    _validate_browser_capture_ids(
        [item.capture_id for item in capture_attachments],
        user_id=user_id,
        captures=captures,
    )
    turn = repository.create_pending_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        client_turn_id=payload.client_turn_id,
        question=turn_question,
        context_attachments=effective_attachments,
        retry_of_turn_id=retry_source.turn_id if retry_source is not None else None,
    )
    if turn is None:
        raise _not_found()
    if turn.status != "pending":
        return turn

    recent_turns = repository.list_turns(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=12,
        before_sequence=turn.sequence,
    )
    effective_question, conversation_command = resolve_conversation_command(
        turn.question,
        recent_turns=recent_turns,
    )
    resolution = resolve_llm_provider(payload.llm_provider)
    attachment_sources: list[ChatSource] = [
        *(["search_results"] if search_attachments or capture_attachments else []),
        *(["saved_jobs"] if saved_job_attachments else []),
    ]
    context_manifest = _build_agent_context_manifest(
        conversation,
        user_id=user_id,
        recent_turns=recent_turns,
        attachment_sources=attachment_sources,
    )
    with langfuse_agent_trace(
        "chat.turn",
        metadata={"provider": resolution.provider, "data_access_mode": conversation.data_access_mode},
        user_id=user_id,
        session_id=conversation_id,
        tags=["chat", "content-redacted"],
    ):
        refusal_route = hard_refusal_route(effective_question)
        agent_step = None
        agent_warning = None
        if refusal_route is None:
            with llm_observation_context(
                "chat.agent.select",
                metadata={"force_content_redacted": True},
                context_parts={"recent_turn_count": len(recent_turns)},
            ):
                agent_step, agent_warning = request_chat_agent_step(
                    effective_question,
                    conversation=conversation,
                    recent_turns=recent_turns,
                    context_manifest=context_manifest,
                    evidence=[],
                    llm_service=resolution.service,
                )
        policy_tools = (
            default_agent_tools(
                effective_question,
                conversation=conversation,
                context_manifest=context_manifest,
            )
            if refusal_route is None
            else []
        )
        requested_tools = list(dict.fromkeys([
            *policy_tools,
            *(agent_step.tool_calls if agent_step is not None and agent_step.action == "use_tools" else []),
        ]))
        retrieval_plan = build_agent_retrieval_plan(
            effective_question,
            tool_calls=requested_tools,
            conversation=conversation,
            recent_turns=recent_turns,
            attachment_sources=attachment_sources if refusal_route is None else [],
        )
        attachment_refs = [
            f"search_result:{item.job_search_run_id}:{item.job_result_id}"
            for item in search_attachments
        ] + [
            f"saved_job:{item.saved_job_id}"
            for item in saved_job_attachments
        ] + [
            f"search_result:browser_capture:{item.capture_id}"
            for item in capture_attachments
        ]
        resolved_retrieval = resolve_chat_retrieval(
            retrieval_plan,
            recent_turns=recent_turns,
            attachment_refs=attachment_refs,
        )
        route = refusal_route or derive_agent_route(
            effective_question,
            sources=retrieval_plan.agent_sources,
            tool_calls=requested_tools,
            reason=(
                "agent_tool_selection"
                if agent_step is not None and agent_step.action == "use_tools"
                else "deterministic_tool_policy" if requested_tools or attachment_sources
                else "agent_direct_answer"
            ),
        )
        try:
            evidence, context_warnings = (
                build_chat_evidence_with_personal_knowledge(
                    effective_question,
                    user_id=user_id,
                    conversation=conversation,
                    requested_sources=resolved_retrieval.sources,
                    active_refs=resolved_retrieval.active_refs,
                    semantic_sources=retrieval_plan.agent_sources,
                    personal_knowledge_requested=(
                        "search_personal_knowledge" in requested_tools
                    ),
                )
                if route.domain == "in_scope" and route.retrieval
                else ([], [])
            )
        except Exception as exc:
            repository.fail_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                turn_id=turn.turn_id,
                fallback_reason=f"context_retrieval_failed:{type(exc).__name__}",
            )
            raise JobAgentError(
                message="Chat context could not be loaded.",
                error_code="chat_context_retrieval_failed",
                status_code=500,
            ) from exc
        answer_warnings: list[str] = []
        answer_fallback: str | None = None
        if refusal_route is not None:
            answer, citations, mode, answer_fallback = (
                HARD_REFUSAL_ANSWER,
                [],
                "refused",
                refusal_route.reason,
            )
        elif (
            agent_step is not None
            and agent_step.action == "final"
            and not evidence
            and not retrieval_plan.requests
        ):
            answer, citations, mode = agent_step.answer, [], "llm"
            answer_warnings = agent_step.limitations
        else:
            with llm_observation_context(
                "chat.agent.answer",
                metadata={"force_content_redacted": True, "route_domain": route.domain},
                context_parts={"evidence_count": len(evidence), "recent_turn_count": len(recent_turns)},
            ):
                final_step, final_warning = request_chat_agent_step(
                    effective_question,
                    conversation=conversation,
                    recent_turns=recent_turns,
                    context_manifest=context_manifest,
                    evidence=evidence,
                    llm_service=resolution.service,
                    require_final=True,
                )
            if final_step is not None:
                citations = citations_for_agent_step(final_step, evidence)
            else:
                citations = []
            if final_step is not None and (not evidence or citations):
                answer, mode = final_step.answer, "llm"
                answer_warnings = final_step.limitations
            else:
                answer, citations = deterministic_chat_answer(evidence)
                mode = "fallback"
                answer_fallback = final_warning or "agent_answer_missing_citations"
    warnings = [*context_warnings, *answer_warnings]
    if agent_warning:
        warnings.append(agent_warning)
    if conversation_command:
        warnings.append(f"conversation_command:{conversation_command}")
    completed = repository.complete_turn(
        user_id=user_id,
        turn=turn,
        route=route,
        retrieval_plan=retrieval_plan,
        answer=answer,
        retrieval_used=bool(evidence),
        retrieved_refs=[item.citation.citation_id for item in evidence],
        citations=citations,
        analysis_mode=mode,
        analysis_provider=resolution.provider,
        fallback_reason=answer_fallback,
        quality_warnings=warnings,
    )
    if completed is None:
        repository.fail_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=turn.turn_id,
            fallback_reason="turn_persistence_failed",
        )
        raise JobAgentError(
            message="Chat turn could not be saved.",
            error_code="chat_turn_persistence_failed",
            status_code=500,
        )
    _maybe_compact(
        user_id=user_id,
        conversation_id=conversation_id,
        llm_service=resolution.service,
        repository=repository,
    )
    return completed


def attach_chat_search_result(
    conversation_id: str,
    ref: ChatSearchResultRef,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> ChatConversation:
    _validate_search_result_refs([ref], user_id=user_id)
    try:
        updated = repository.pin_search_result(
            user_id=user_id,
            conversation_id=conversation_id,
            ref=ref,
        )
    except OverflowError:
        raise JobAgentError(
            message="A conversation can pin at most 20 search results.",
            error_code="chat_context_limit_reached",
            status_code=422,
        ) from None
    if updated is None:
        raise _not_found()
    return updated


def attach_chat_browser_capture(
    conversation_id: str,
    ref: ChatBrowserCaptureAttachment,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> ChatConversation:
    _validate_browser_capture_ids([ref.capture_id], user_id=user_id, captures=captures)
    conversation = get_chat_conversation(conversation_id, user_id=user_id, repository=repository)
    capture_ids = conversation.data_scope.browser_capture_ids
    if ref.capture_id in capture_ids:
        return conversation
    if len(capture_ids) >= 5:
        raise JobAgentError(
            message="A conversation can attach at most 5 browser JD captures.",
            error_code="chat_context_limit_reached",
            status_code=422,
        )
    scope = conversation.data_scope.model_copy(update={
        "browser_capture_ids": [*capture_ids, ref.capture_id],
    })
    updated = repository.update_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        payload=ChatConversationUpdateRequest(data_scope=scope),
    )
    if updated is None:
        raise _not_found()
    return updated


def detach_chat_search_result(
    conversation_id: str,
    ref: ChatSearchResultRef,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> ChatConversation:
    conversation = get_chat_conversation(conversation_id, user_id=user_id, repository=repository)
    remaining = [
        item for item in conversation.data_scope.job_search_result_refs
        if not (
            item.job_search_run_id == ref.job_search_run_id
            and item.job_result_id == ref.job_result_id
        )
    ]
    scope = conversation.data_scope.model_copy(update={"job_search_result_refs": remaining})
    updated = repository.update_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        payload=ChatConversationUpdateRequest(data_scope=scope),
    )
    if updated is None:
        raise _not_found()
    return updated


def delete_chat_turn(
    conversation_id: str,
    turn_id: str,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> None:
    get_chat_conversation(conversation_id, user_id=user_id, repository=repository)
    if not repository.delete_turn(
        user_id=user_id, conversation_id=conversation_id, turn_id=turn_id
    ):
        raise _not_found()


def clear_chat_memory(
    conversation_id: str,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> None:
    if not repository.clear_memory(user_id=user_id, conversation_id=conversation_id):
        raise _not_found()


def delete_chat_conversation(
    conversation_id: str,
    *,
    user_id: str,
    repository: ChatRepository = chat_repository,
) -> None:
    if not repository.delete_conversation(user_id=user_id, conversation_id=conversation_id):
        raise _not_found()


def _maybe_compact(
    *,
    user_id: str,
    conversation_id: str,
    llm_service,
    repository: ChatRepository,
) -> None:
    conversation = repository.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if conversation is None:
        return
    turns = [item for item in repository.list_turns(
        user_id=user_id, conversation_id=conversation_id, limit=200
    ) if item.status == "completed"]
    total_chars = sum(len(item.question) + len(item.answer or "") for item in turns)
    if len(turns) < 12 and total_chars < 12_000:
        return
    source_turns = turns[:-4]
    if not source_turns or source_turns[-1].sequence <= conversation.summary_through_sequence:
        return
    with llm_observation_context(
        "chat.compact",
        metadata={"force_content_redacted": True},
        context_parts={"source_turn_count": len(source_turns)},
    ):
        summary = compress_chat_memory(source_turns, llm_service=llm_service)
    repository.update_summary(
        user_id=user_id,
        conversation_id=conversation_id,
        summary=summary,
        through_sequence=source_turns[-1].sequence,
    )


def _validate_data_scope(
    scope: ChatDataScope,
    *,
    user_id: str,
    profiles: ResumeProfileRepository = resume_profile_repository,
    searches: JobSearchRepository = job_search_repository,
    saved_jobs: SavedJobRepository = saved_job_repository,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> None:
    if scope.resume_profile_id and profiles.get(
        user_id=user_id, resume_profile_id=scope.resume_profile_id
    ) is None:
        raise _resource_not_found()
    if any(searches.get(run_id, user_id=user_id) is None for run_id in scope.job_search_run_ids):
        raise _resource_not_found()
    _validate_search_result_refs(
        scope.job_search_result_refs,
        user_id=user_id,
        searches=searches,
    )
    if any(saved_jobs.get(user_id=user_id, saved_job_id=item) is None for item in scope.saved_job_ids):
        raise _resource_not_found()
    _validate_browser_capture_ids(
        scope.browser_capture_ids,
        user_id=user_id,
        captures=captures,
    )


def _validate_search_result_refs(
    refs: Sequence[ChatSearchResultRef],
    *,
    user_id: str,
    searches: JobSearchRepository = job_search_repository,
) -> None:
    result_ids_by_run: dict[str, set[str]] = {}
    for ref in refs:
        result_ids_by_run.setdefault(ref.job_search_run_id, set()).add(ref.job_result_id)
    for run_id, result_ids in result_ids_by_run.items():
        run = searches.get(run_id, user_id=user_id)
        available_ids = {item.job_result_id for item in run.results} if run is not None else set()
        if run is None or not result_ids.issubset(available_ids):
            raise _resource_not_found()


def _validate_saved_job_ids(
    saved_job_ids: Sequence[str],
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
) -> None:
    if any(
        saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id) is None
        for saved_job_id in saved_job_ids
    ):
        raise _resource_not_found()


def _validate_browser_capture_ids(
    capture_ids: Sequence[str],
    *,
    user_id: str,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> None:
    if any(captures.get(user_id=user_id, capture_id=item) is None for item in capture_ids):
        raise _resource_not_found()


def _build_agent_context_manifest(
    conversation: ChatConversation,
    *,
    user_id: str,
    recent_turns: list[ChatTurn],
    attachment_sources: list[ChatSource],
) -> dict[str, object]:
    data_access_enabled = conversation.data_access_mode != "off"
    pinned = (
        _resolve_pinned_memory_resources(
            conversation.data_scope,
            user_id=user_id,
            profiles=resume_profile_repository,
            searches=job_search_repository,
            saved_jobs=saved_job_repository,
            captures=browser_job_capture_repository,
        )
        if data_access_enabled
        else []
    )
    previous_turn = next(
        (item for item in reversed(recent_turns) if item.status == "completed" and item.retrieval_used),
        None,
    )
    return {
        "data_access_mode": conversation.data_access_mode,
        "allowed_sources": conversation.data_scope.allowed_sources,
        "pinned_context": [
            {
                "source_type": item.source_type,
                "label": item.label,
                "status": item.status,
            }
            for item in pinned
        ],
        "previous_references": [
            {
                "source_type": item.source_type,
                "label": item.label,
            }
            for item in (
                previous_turn.citations
                if data_access_enabled and previous_turn is not None
                else []
            )
        ],
        "current_attachment_sources": (
            list(dict.fromkeys(attachment_sources)) if data_access_enabled else []
        ),
    }


def _resolve_pinned_memory_resources(
    scope: ChatDataScope,
    *,
    user_id: str,
    profiles: ResumeProfileRepository,
    searches: JobSearchRepository,
    saved_jobs: SavedJobRepository,
    captures: BrowserJobCaptureRepository,
) -> list[ChatMemoryResource]:
    resources: list[ChatMemoryResource] = []
    if scope.resume_profile_id:
        profile = profiles.get(user_id=user_id, resume_profile_id=scope.resume_profile_id)
        resources.append(ChatMemoryResource(
            source_type="profile",
            resource_id=scope.resume_profile_id,
            label=profile.name if profile is not None else "Unavailable profile",
            status="available" if profile is not None else "unavailable",
        ))
    result_run_ids = {ref.job_search_run_id for ref in scope.job_search_result_refs}
    for run_id in scope.job_search_run_ids:
        if run_id in result_run_ids:
            continue
        run = searches.get(run_id, user_id=user_id)
        resources.append(ChatMemoryResource(
            source_type="search_results",
            resource_id=run_id,
            label=_search_run_label(run.query, len(run.results)) if run is not None else "Unavailable search run",
            status="available" if run is not None else "unavailable",
        ))
    for ref in scope.job_search_result_refs:
        run = searches.get(ref.job_search_run_id, user_id=user_id)
        result = next(
            (item for item in run.results if item.job_result_id == ref.job_result_id),
            None,
        ) if run is not None else None
        resources.append(ChatMemoryResource(
            source_type="search_results",
            resource_id=ref.job_result_id,
            label=(
                f"{result.title} · {result.company}"
                if result is not None
                else "Unavailable search result"
            ),
            status="available" if result is not None else "unavailable",
        ))
    for saved_job_id in scope.saved_job_ids:
        job = saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id)
        resources.append(ChatMemoryResource(
            source_type="saved_jobs",
            resource_id=saved_job_id,
            label=(
                f"{job.title} · {job.company or 'Unknown company'}"
                if job is not None
                else "Unavailable saved job"
            ),
            status="available" if job is not None else "unavailable",
        ))
    for capture_id in scope.browser_capture_ids:
        capture = captures.get(user_id=user_id, capture_id=capture_id)
        resources.append(ChatMemoryResource(
            source_type="search_results",
            resource_id=capture_id,
            label=(
                f"{capture.title or capture.page_title} · {capture.company or 'Unknown company'}"
                if capture is not None
                else "Unavailable browser JD capture"
            ),
            status="available" if capture is not None else "unavailable",
        ))
    return resources


def _citation_is_available(
    citation_id: str,
    *,
    source_type: ChatSource,
    resource_id: str,
    user_id: str,
    conversation_id: str,
    repository: ChatRepository,
    profiles: ResumeProfileRepository,
    searches: JobSearchRepository,
    saved_jobs: SavedJobRepository,
    captures: BrowserJobCaptureRepository,
) -> bool:
    if source_type == "profile":
        return profiles.get(user_id=user_id, resume_profile_id=resource_id) is not None
    if source_type == "saved_jobs":
        return saved_jobs.get(user_id=user_id, saved_job_id=resource_id) is not None
    if source_type == "chat_history":
        return repository.get_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=resource_id,
        ) is not None
    if source_type == "search_results":
        parts = citation_id.split(":", 2)
        if len(parts) != 3:
            return False
        if parts[1] == "browser_capture":
            return captures.get(user_id=user_id, capture_id=resource_id) is not None
        run = searches.get(parts[1], user_id=user_id)
        return run is not None and any(
            item.job_result_id == resource_id for item in run.results
        )
    return False


def _not_found() -> JobAgentError:
    return JobAgentError(
        message="Chat conversation or turn not found.",
        error_code="chat_resource_not_found",
        status_code=404,
    )


def _resource_not_found() -> JobAgentError:
    return JobAgentError(
        message="One or more selected chat resources are unavailable.",
        error_code="chat_context_resource_not_found",
        status_code=404,
    )


def _search_run_label(query: str, result_count: int) -> str:
    compact = " ".join(query.split())
    label = compact[:70] + ("…" if len(compact) > 70 else "")
    return f"{label} · {result_count} results"
