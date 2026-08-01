from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_chat_or_browser_helper_user, get_current_user
from app.application.chat_usecases import (
    attach_chat_saved_job,
    attach_chat_search_result,
    clear_chat_memory,
    create_chat_conversation,
    create_chat_turn,
    delete_chat_conversation,
    delete_chat_turn,
    detach_chat_search_result,
    get_chat_conversation,
    get_chat_context_catalog,
    get_chat_memory_status,
    list_chat_conversations,
    list_chat_turns,
    update_chat_conversation,
)
from app.schemas.auth import UserAccount
from app.schemas.chat import (
    ChatConversation,
    ChatConversationCreateRequest,
    ChatConversationListResponse,
    ChatConversationUpdateRequest,
    ChatContextCatalog,
    ChatMemoryStatus,
    ChatSavedJobAttachment,
    ChatSearchResultRef,
    ChatTurn,
    ChatTurnCreateRequest,
    ChatTurnListResponse,
)


router = APIRouter(prefix="/api/v1/chat/conversations", tags=["chat"])
context_router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@context_router.get("/context-catalog", response_model=ChatContextCatalog)
def get_chat_context_catalog_endpoint(
    current_user: UserAccount = Depends(get_current_user),
) -> ChatContextCatalog:
    return get_chat_context_catalog(user_id=current_user.user_id)


@router.post("", response_model=ChatConversation, status_code=status.HTTP_201_CREATED)
def create_chat_conversation_endpoint(
    payload: ChatConversationCreateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> ChatConversation:
    return create_chat_conversation(payload, user_id=current_user.user_id)


@router.get("", response_model=ChatConversationListResponse)
def list_chat_conversations_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> ChatConversationListResponse:
    return ChatConversationListResponse(
        items=list_chat_conversations(user_id=current_user.user_id, limit=limit)
    )


@router.get("/{conversation_id}", response_model=ChatConversation)
def get_chat_conversation_endpoint(
    conversation_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ChatConversation:
    return get_chat_conversation(conversation_id, user_id=current_user.user_id)


@router.patch("/{conversation_id}", response_model=ChatConversation)
def update_chat_conversation_endpoint(
    conversation_id: str,
    payload: ChatConversationUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> ChatConversation:
    return update_chat_conversation(conversation_id, payload, user_id=current_user.user_id)


@router.get("/{conversation_id}/turns", response_model=ChatTurnListResponse)
def list_chat_turns_endpoint(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_sequence: int | None = Query(default=None, ge=1),
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> ChatTurnListResponse:
    return ChatTurnListResponse(items=list_chat_turns(
        conversation_id,
        user_id=current_user.user_id,
        limit=limit,
        before_sequence=before_sequence,
    ))


@router.get("/{conversation_id}/memory", response_model=ChatMemoryStatus)
def get_chat_memory_status_endpoint(
    conversation_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ChatMemoryStatus:
    return get_chat_memory_status(conversation_id, user_id=current_user.user_id)


@router.post("/{conversation_id}/turns", response_model=ChatTurn)
def create_chat_turn_endpoint(
    conversation_id: str,
    payload: ChatTurnCreateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> ChatTurn:
    return create_chat_turn(conversation_id, payload, user_id=current_user.user_id)


@router.delete("/{conversation_id}/turns/{turn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_turn_endpoint(
    conversation_id: str,
    turn_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    delete_chat_turn(conversation_id, turn_id, user_id=current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{conversation_id}/memory", status_code=status.HTTP_204_NO_CONTENT)
def clear_chat_memory_endpoint(
    conversation_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    clear_chat_memory(conversation_id, user_id=current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_conversation_endpoint(
    conversation_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    delete_chat_conversation(conversation_id, user_id=current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/context/search-results", response_model=ChatConversation)
def attach_chat_search_result_endpoint(
    conversation_id: str,
    payload: ChatSearchResultRef,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> ChatConversation:
    return attach_chat_search_result(conversation_id, payload, user_id=current_user.user_id)


@router.post("/{conversation_id}/context/saved-jobs", response_model=ChatConversation)
def attach_chat_saved_job_endpoint(
    conversation_id: str,
    payload: ChatSavedJobAttachment,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> ChatConversation:
    return attach_chat_saved_job(
        conversation_id,
        payload,
        user_id=current_user.user_id,
    )


@router.delete(
    "/{conversation_id}/context/search-results/{job_search_run_id}/{job_result_id}",
    response_model=ChatConversation,
)
def detach_chat_search_result_endpoint(
    conversation_id: str,
    job_search_run_id: str,
    job_result_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ChatConversation:
    return detach_chat_search_result(
        conversation_id,
        ChatSearchResultRef(
            job_search_run_id=job_search_run_id,
            job_result_id=job_result_id,
        ),
        user_id=current_user.user_id,
    )
