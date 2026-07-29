from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Collection
from urllib.parse import urlparse

import httpx
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client


class MCPClientError(RuntimeError):
    """Base error for bounded backend-to-MCP communication."""


class MCPConfigurationError(MCPClientError):
    pass


class MCPConnectionError(MCPClientError):
    pass


class MCPContractError(MCPClientError):
    pass


class MCPToolCallError(MCPClientError):
    pass


@dataclass(frozen=True)
class MCPToolInfo:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class MCPServerInspection:
    server_name: str
    server_version: str | None
    protocol_version: str
    tools: tuple[MCPToolInfo, ...]


@dataclass(frozen=True)
class MCPToolCallResult:
    tool_name: str
    structured_content: object | None
    text_content: tuple[str, ...]
    non_text_content_count: int


class StreamableHTTPMCPClient:
    """Bounded MCP client for one backend-configured Streamable HTTP service."""

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 10.0,
        allowed_tools: Collection[str] = (),
        max_response_chars: int = 500_000,
    ) -> None:
        self.url = _validated_url(url)
        if not 0 < timeout_seconds <= 60:
            raise MCPConfigurationError(
                "MCP timeout must be greater than 0 and at most 60 seconds"
            )
        if max_response_chars < 1:
            raise MCPConfigurationError("MCP response limit must be positive")
        self.timeout_seconds = timeout_seconds
        self.allowed_tools = frozenset(allowed_tools)
        self.max_response_chars = max_response_chars

    async def inspect(
        self,
        *,
        required_tools: Collection[str] = (),
    ) -> MCPServerInspection:
        try:
            return await asyncio.wait_for(
                self._inspect(required_tools=frozenset(required_tools)),
                timeout=self.timeout_seconds,
            )
        except MCPClientError:
            raise
        except TimeoutError as exc:
            raise MCPConnectionError("MCP service inspection timed out") from exc
        except Exception as exc:
            raise MCPConnectionError(_connection_error_message(exc)) from exc

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolCallResult:
        if name not in self.allowed_tools:
            raise MCPConfigurationError(f"MCP tool is not allowed: {name}")
        try:
            return await asyncio.wait_for(
                self._call_tool(name, arguments or {}),
                timeout=self.timeout_seconds,
            )
        except MCPClientError:
            raise
        except TimeoutError as exc:
            raise MCPConnectionError("MCP tool call timed out") from exc
        except Exception as exc:
            raise MCPConnectionError(_connection_error_message(exc)) from exc

    async def _inspect(
        self,
        *,
        required_tools: frozenset[str],
    ) -> MCPServerInspection:
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(self.timeout_seconds, 2.0),
        )
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as http_client:
            async with streamable_http_client(
                self.url,
                http_client=http_client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    initialized = await session.initialize()
                    listed = await session.list_tools()

        tools = tuple(
            MCPToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.inputSchema),
            )
            for tool in listed.tools
        )
        available_tools = {tool.name for tool in tools}
        missing_tools = sorted(required_tools - available_tools)
        if missing_tools:
            raise MCPContractError(
                f"MCP service is missing required tools: {', '.join(missing_tools)}"
            )

        server_info = initialized.serverInfo
        return MCPServerInspection(
            server_name=server_info.name,
            server_version=getattr(server_info, "version", None),
            protocol_version=str(initialized.protocolVersion),
            tools=tools,
        )

    async def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> MCPToolCallResult:
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(self.timeout_seconds, 2.0),
        )
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as http_client:
            async with streamable_http_client(
                self.url,
                http_client=http_client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments=arguments)

        text_content = tuple(
            block.text
            for block in result.content
            if isinstance(block, types.TextContent)
        )
        if result.isError:
            detail = next(
                (text.strip() for text in text_content if text.strip()),
                "MCP tool returned an error",
            )
            raise MCPToolCallError(f"{name}: {detail[:300]}")

        response_size = len(json.dumps(
            result.structuredContent,
            ensure_ascii=False,
            default=str,
        ))
        response_size += sum(_content_size(block) for block in result.content)
        if response_size > self.max_response_chars:
            raise MCPContractError(
                f"MCP tool response exceeded {self.max_response_chars} characters"
            )

        return MCPToolCallResult(
            tool_name=name,
            structured_content=result.structuredContent,
            text_content=text_content,
            non_text_content_count=len(result.content) - len(text_content),
        )


def _validated_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MCPConfigurationError("MCP URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise MCPConfigurationError("MCP URL must not contain credentials")
    if parsed.fragment:
        raise MCPConfigurationError("MCP URL must not contain a fragment")
    return url


def _connection_error_message(error: BaseException) -> str:
    leaves = list(_leaf_exceptions(error))
    if any(isinstance(item, httpx.TimeoutException) for item in leaves):
        return "MCP service request timed out"
    if any(isinstance(item, (httpx.ConnectError, OSError)) for item in leaves):
        return "MCP service is unavailable"
    names = ", ".join(dict.fromkeys(type(item).__name__ for item in leaves))
    return f"MCP service request failed: {names or type(error).__name__}"


def _content_size(block: object) -> int:
    value = getattr(block, "text", None)
    if value is None:
        value = getattr(block, "data", None)
    return len(value) if isinstance(value, (str, bytes)) else len(str(value or ""))


def _leaf_exceptions(error: BaseException):
    if isinstance(error, BaseExceptionGroup):
        for nested in error.exceptions:
            yield from _leaf_exceptions(nested)
        return
    yield error
