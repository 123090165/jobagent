"""回归验证mcp service client的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from mcp import types

import app.services.mcp.client as client_module
from app.services.mcp import (
    MCPConfigurationError,
    MCPContractError,
    MCPServerInspection,
    MCPToolCallResult,
    ModularRAGMCP,
    StreamableHTTPMCPClient,
)
from app.services.mcp.modular_rag import (
    MODULAR_RAG_REQUIRED_TOOLS,
    resolve_modular_rag_client,
)


class _FakeSession:
    def __init__(self, read_stream, write_stream) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def initialize(self):
        return SimpleNamespace(
            serverInfo=SimpleNamespace(
                name="modular-rag-mcp-server",
                version="0.1.0",
            ),
            protocolVersion="2025-03-26",
        )

    async def list_tools(self):
        return SimpleNamespace(tools=[
            SimpleNamespace(
                name=name,
                description=f"{name} description",
                inputSchema={"type": "object"},
            )
            for name in MODULAR_RAG_REQUIRED_TOOLS
        ])

    async def call_tool(self, name, *, arguments):
        return SimpleNamespace(
            isError=False,
            structuredContent={"collections": ["knowledge_hub"]},
            content=[
                types.TextContent(
                    type="text",
                    text='{"collections":["knowledge_hub"]}',
                )
            ],
        )


@asynccontextmanager
async def _fake_transport(url, *, http_client):
    yield object(), object(), None


def test_client_rejects_non_http_urls() -> None:
    with pytest.raises(MCPConfigurationError):
        StreamableHTTPMCPClient("file:///tmp/rag-mcp")


def test_resolver_disables_unconfigured_service(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_RAG_MCP_URL", raising=False)

    assert resolve_modular_rag_client() is None


def test_resolver_reads_backend_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "JOBAGENT_RAG_MCP_URL",
        "http://127.0.0.1:8002/mcp",
    )
    monkeypatch.setenv("JOBAGENT_RAG_MCP_TIMEOUT_SECONDS", "7.5")

    client = resolve_modular_rag_client()

    assert client is not None
    assert client.url == "http://127.0.0.1:8002/mcp"
    assert client.timeout_seconds == 7.5
    assert client.allowed_tools == MODULAR_RAG_REQUIRED_TOOLS


def test_client_initializes_and_lists_required_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        client_module,
        "streamable_http_client",
        _fake_transport,
    )
    monkeypatch.setattr(client_module, "ClientSession", _FakeSession)
    client = StreamableHTTPMCPClient("http://127.0.0.1:8002/mcp")

    inspection = asyncio.run(client.inspect(
        required_tools=MODULAR_RAG_REQUIRED_TOOLS,
    ))

    assert inspection.server_name == "modular-rag-mcp-server"
    assert inspection.protocol_version == "2025-03-26"
    assert {tool.name for tool in inspection.tools} == MODULAR_RAG_REQUIRED_TOOLS


def test_client_rejects_missing_required_tools(monkeypatch) -> None:
    class MissingToolSession(_FakeSession):
        async def list_tools(self):
            return SimpleNamespace(tools=[])

    monkeypatch.setattr(
        client_module,
        "streamable_http_client",
        _fake_transport,
    )
    monkeypatch.setattr(client_module, "ClientSession", MissingToolSession)
    client = StreamableHTTPMCPClient("http://127.0.0.1:8002/mcp")

    with pytest.raises(MCPContractError, match="missing required tools"):
        asyncio.run(client.inspect(
            required_tools=MODULAR_RAG_REQUIRED_TOOLS,
        ))


def test_client_calls_only_allowlisted_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        client_module,
        "streamable_http_client",
        _fake_transport,
    )
    monkeypatch.setattr(client_module, "ClientSession", _FakeSession)
    client = StreamableHTTPMCPClient(
        "http://127.0.0.1:8002/mcp",
        allowed_tools={"list_collections"},
    )

    result = asyncio.run(client.call_tool("list_collections"))

    assert result.structured_content == {"collections": ["knowledge_hub"]}
    assert result.non_text_content_count == 0
    with pytest.raises(MCPConfigurationError, match="not allowed"):
        asyncio.run(client.call_tool("query_knowledge_hub"))


def test_client_surfaces_tool_errors(monkeypatch) -> None:
    class ErrorSession(_FakeSession):
        async def call_tool(self, name, *, arguments):
            return SimpleNamespace(
                isError=True,
                structuredContent=None,
                content=[
                    types.TextContent(
                        type="text",
                        text="document not found",
                    )
                ],
            )

    monkeypatch.setattr(
        client_module,
        "streamable_http_client",
        _fake_transport,
    )
    monkeypatch.setattr(client_module, "ClientSession", ErrorSession)
    client = StreamableHTTPMCPClient(
        "http://127.0.0.1:8002/mcp",
        allowed_tools={"get_document_summary"},
    )

    with pytest.raises(
        client_module.MCPToolCallError,
        match="document not found",
    ):
        asyncio.run(client.call_tool(
            "get_document_summary",
            {"doc_id": "missing"},
        ))


def test_client_rejects_oversized_tool_results(monkeypatch) -> None:
    class LargeResultSession(_FakeSession):
        async def call_tool(self, name, *, arguments):
            return SimpleNamespace(
                isError=False,
                structuredContent={"value": "x" * 100},
                content=[],
            )

    monkeypatch.setattr(
        client_module,
        "streamable_http_client",
        _fake_transport,
    )
    monkeypatch.setattr(client_module, "ClientSession", LargeResultSession)
    client = StreamableHTTPMCPClient(
        "http://127.0.0.1:8002/mcp",
        allowed_tools={"list_collections"},
        max_response_chars=20,
    )

    with pytest.raises(MCPContractError, match="response exceeded"):
        asyncio.run(client.call_tool("list_collections"))


def test_client_unwraps_connection_failures(monkeypatch) -> None:
    @asynccontextmanager
    async def failed_transport(url, *, http_client):
        raise ExceptionGroup(
            "transport failed",
            [httpx.ConnectError("connection refused")],
        )
        yield

    monkeypatch.setattr(
        client_module,
        "streamable_http_client",
        failed_transport,
    )
    client = StreamableHTTPMCPClient("http://127.0.0.1:8002/mcp")

    with pytest.raises(
        client_module.MCPConnectionError,
        match="service is unavailable",
    ):
        asyncio.run(client.inspect())


class _FakeMCPClient:
    def __init__(self) -> None:
        self.calls = []

    async def inspect(self, *, required_tools):
        return MCPServerInspection(
            server_name="modular-rag-mcp-server",
            server_version="0.1.0",
            protocol_version="2025-11-25",
            tools=(),
        )

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        payloads = {
            "list_collections": {"collections": ["career"]},
            "query_knowledge_hub": {
                "results": [{
                    "chunk_id": "chunk-1",
                    "score": 0.91,
                    "text": "Hybrid retrieval combines dense and sparse search.",
                    "metadata": {
                        "collection": "career",
                        "source_path": "guide.pdf",
                    },
                }]
            },
            "search_authorized_knowledge": {
                "results": [{
                    "chunk_id": "private-chunk",
                    "score": 0.95,
                    "text": "Private profile evidence.",
                    "metadata": {
                        "tenant_id": "default",
                        "owner_user_id": "user-a",
                        "visibility": "private",
                    },
                }]
            },
            "get_document_summary": {
                "doc_id": "guide.pdf",
                "source_path": "guide.pdf",
                "chunk_count": 2,
                "title": "Guide",
                "summary": "A retrieval guide.",
                "metadata": {"collection": "career"},
            },
        }
        return MCPToolCallResult(
            tool_name=name,
            structured_content=payloads[name],
            text_content=(),
            non_text_content_count=0,
        )


def test_modular_rag_adapter_validates_all_tool_results() -> None:
    client = _FakeMCPClient()
    service = ModularRAGMCP(client)

    collections = asyncio.run(service.list_collections())
    query = asyncio.run(service.query(
        "hybrid retrieval",
        top_k=3,
        collection="career",
    ))
    summary = asyncio.run(service.get_document_summary("guide.pdf"))

    assert collections.collections == ["career"]
    assert query.results[0].chunk_id == "chunk-1"
    assert summary.chunk_count == 2
    assert client.calls == [
        ("list_collections", None),
        (
            "query_knowledge_hub",
            {
                "query": "hybrid retrieval",
                "top_k": 3,
                "filters": {"collection": "career"},
            },
        ),
        ("get_document_summary", {"doc_id": "guide.pdf"}),
    ]


def test_modular_rag_adapter_issues_signed_scope_for_private_query() -> None:
    client = _FakeMCPClient()
    service = ModularRAGMCP(client, scope_secret="shared-secret")

    result = asyncio.run(service.query_for_user(
        "my python experience",
        user_id="user-a",
        resource_types=("resume_profile",),
    ))

    name, arguments = client.calls[0]
    assert name == "search_authorized_knowledge"
    assert arguments["scope_token"].count(".") == 1
    assert result.results[0].metadata["owner_user_id"] == "user-a"


def test_modular_rag_adapter_validates_server_identity() -> None:
    class WrongServerClient(_FakeMCPClient):
        async def inspect(self, *, required_tools):
            return MCPServerInspection(
                server_name="unexpected-server",
                server_version="1.0",
                protocol_version="2025-11-25",
                tools=(),
            )

    with pytest.raises(MCPContractError, match="not the Modular RAG"):
        asyncio.run(ModularRAGMCP(WrongServerClient()).inspect())


def test_modular_rag_adapter_rejects_incompatible_payload() -> None:
    class InvalidClient(_FakeMCPClient):
        async def call_tool(self, name, arguments=None):
            return MCPToolCallResult(
                tool_name=name,
                structured_content={"unexpected": True},
                text_content=(),
                non_text_content_count=0,
            )

    service = ModularRAGMCP(InvalidClient())

    with pytest.raises(MCPContractError, match="incompatible response"):
        asyncio.run(service.get_document_summary("guide.pdf"))


def test_modular_rag_adapter_bounds_query_parameters() -> None:
    service = ModularRAGMCP(_FakeMCPClient())

    with pytest.raises(MCPConfigurationError, match="parameters are invalid"):
        asyncio.run(service.query("hybrid retrieval", top_k=21))
