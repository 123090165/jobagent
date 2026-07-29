from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas.knowledge import (
    KnowledgeCollections,
    KnowledgeDocumentSummary,
    KnowledgeQueryRequest,
    KnowledgeQueryResult,
)

from .client import (
    MCPConfigurationError,
    MCPContractError,
    MCPServerInspection,
    StreamableHTTPMCPClient,
)
from .rag_scope_token import issue_rag_scope_token


MODULAR_RAG_REQUIRED_TOOLS = frozenset({
    "query_knowledge_hub",
    "list_collections",
    "get_document_summary",
    "search_authorized_knowledge",
})
MODULAR_RAG_SERVER_NAME = "modular-rag-mcp-server"
ModelT = TypeVar("ModelT", bound=BaseModel)


class ModularRAGMCP:
    def __init__(
        self,
        client: StreamableHTTPMCPClient,
        *,
        scope_secret: str | None = None,
    ) -> None:
        self.client = client
        self.scope_secret = scope_secret

    async def inspect(self) -> MCPServerInspection:
        inspection = await self.client.inspect(
            required_tools=MODULAR_RAG_REQUIRED_TOOLS
        )
        if inspection.server_name != MODULAR_RAG_SERVER_NAME:
            raise MCPContractError(
                "Configured MCP endpoint is not the Modular RAG service"
            )
        return inspection

    async def list_collections(self) -> KnowledgeCollections:
        result = await self.client.call_tool("list_collections")
        return _validate_payload(
            KnowledgeCollections,
            result.structured_content,
            tool_name="list_collections",
        )

    async def query(
        self,
        query: str,
        *,
        top_k: int = 5,
        collection: str | None = None,
    ) -> KnowledgeQueryResult:
        try:
            request = KnowledgeQueryRequest(
                query=query,
                top_k=top_k,
                collection=collection,
            )
        except ValidationError as exc:
            raise MCPConfigurationError(
                "Knowledge query parameters are invalid"
            ) from exc
        filters = (
            {"collection": request.collection}
            if request.collection is not None
            else None
        )
        result = await self.client.call_tool(
            "query_knowledge_hub",
            {
                "query": request.query,
                "top_k": request.top_k,
                "filters": filters,
            },
        )
        return _validate_payload(
            KnowledgeQueryResult,
            result.structured_content,
            tool_name="query_knowledge_hub",
        )

    async def get_document_summary(
        self,
        doc_id: str,
    ) -> KnowledgeDocumentSummary:
        normalized_doc_id = doc_id.strip()
        if not normalized_doc_id or len(normalized_doc_id) > 1_000:
            raise MCPConfigurationError(
                "Document id must contain between 1 and 1000 characters"
            )
        result = await self.client.call_tool(
            "get_document_summary",
            {"doc_id": normalized_doc_id},
        )
        return _validate_payload(
            KnowledgeDocumentSummary,
            result.structured_content,
            tool_name="get_document_summary",
        )

    async def query_for_user(
        self,
        query: str,
        *,
        user_id: str,
        resource_types: tuple[str, ...] = ("resume_profile", "saved_job"),
        top_k: int = 5,
        include_public: bool = True,
    ) -> KnowledgeQueryResult:
        if not self.scope_secret:
            raise MCPConfigurationError(
                "JOBAGENT_RAG_SERVICE_TOKEN is required for private retrieval"
            )
        try:
            normalized_user_id = user_id.strip()
            allowed_resource_types = {"resume_profile", "saved_job"}
            if (
                not normalized_user_id
                or not resource_types
                or any(value not in allowed_resource_types for value in resource_types)
            ):
                raise ValueError("invalid authorized retrieval scope")
            request = KnowledgeQueryRequest(query=query, top_k=top_k)
            scope_token = issue_rag_scope_token(
                secret=self.scope_secret,
                user_id=normalized_user_id,
                resource_types=resource_types,
                include_public=include_public,
            )
        except (ValidationError, ValueError) as exc:
            raise MCPConfigurationError(
                "Authorized knowledge query parameters are invalid"
            ) from exc
        result = await self.client.call_tool(
            "search_authorized_knowledge",
            {
                "query": request.query,
                "top_k": request.top_k,
                "scope_token": scope_token,
            },
        )
        return _validate_payload(
            KnowledgeQueryResult,
            result.structured_content,
            tool_name="search_authorized_knowledge",
        )


def resolve_modular_rag_client() -> StreamableHTTPMCPClient | None:
    url = os.getenv("JOBAGENT_RAG_MCP_URL", "").strip()
    if not url:
        return None

    raw_timeout = os.getenv("JOBAGENT_RAG_MCP_TIMEOUT_SECONDS", "10").strip()
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise MCPConfigurationError(
            "JOBAGENT_RAG_MCP_TIMEOUT_SECONDS must be numeric"
        ) from exc
    raw_response_limit = os.getenv(
        "JOBAGENT_RAG_MCP_MAX_RESPONSE_CHARS",
        "500000",
    ).strip()
    try:
        max_response_chars = int(raw_response_limit)
    except ValueError as exc:
        raise MCPConfigurationError(
            "JOBAGENT_RAG_MCP_MAX_RESPONSE_CHARS must be an integer"
        ) from exc
    return StreamableHTTPMCPClient(
        url,
        timeout_seconds=timeout_seconds,
        allowed_tools=MODULAR_RAG_REQUIRED_TOOLS,
        max_response_chars=max_response_chars,
    )


def resolve_modular_rag_service() -> ModularRAGMCP | None:
    client = resolve_modular_rag_client()
    return (
        ModularRAGMCP(
            client,
            scope_secret=os.getenv("JOBAGENT_RAG_SERVICE_TOKEN", "").strip() or None,
        )
        if client is not None
        else None
    )


def _validate_payload(
    model: type[ModelT],
    payload: object,
    *,
    tool_name: str,
) -> ModelT:
    if not isinstance(payload, dict):
        raise MCPContractError(
            f"{tool_name} did not return structured object content"
        )
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise MCPContractError(
            f"{tool_name} returned an incompatible response"
        ) from exc
