from __future__ import annotations

import json
import os
from typing import Protocol
from urllib.parse import urlparse

import httpx

from app.schemas.interview_preparation import LearningResource
from app.repositories.learning_resource_repository import (
    LearningResourceRepository,
    learning_resource_repository,
)


class LearningResourceSearch(Protocol):
    async def search(self, topic: str, *, limit: int = 2) -> list[LearningResource]: ...


class LearningResourceSearchError(RuntimeError):
    pass


class MCPStreamableHTTPResourceSearch:
    def __init__(self, url: str, tool_name: str, query_argument: str) -> None:
        self.url = url
        self.tool_name = tool_name
        self.query_argument = query_argument

    async def search(self, topic: str, *, limit: int = 2) -> list[LearningResource]:
        from mcp import ClientSession, types
        from mcp.client.streamable_http import streamable_http_client

        await self._preflight()
        timeout = float(os.getenv("JOBAGENT_LEARNING_MCP_TIMEOUT", "15"))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        self.tool_name,
                        arguments={self.query_argument: f"{topic} official tutorial beginner"},
                    )
        payloads: list[object] = []
        if result.structuredContent:
            payloads.append(result.structuredContent)
        for block in result.content:
            if isinstance(block, types.TextContent):
                try:
                    payloads.append(json.loads(block.text))
                except json.JSONDecodeError:
                    continue
        return _resources_from_payloads(topic, payloads, limit=limit)

    async def _preflight(self) -> None:
        timeout = httpx.Timeout(2.0, connect=1.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.options(self.url)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise LearningResourceSearchError(
                f"mcp_server_unavailable: {urlparse(self.url).netloc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LearningResourceSearchError("mcp_preflight_timeout") from exc
        if response.status_code == 404:
            raise LearningResourceSearchError("mcp_endpoint_not_found")


class OfficialCatalogResourceSearch:
    async def search(self, topic: str, *, limit: int = 2) -> list[LearningResource]:
        normalized = topic.casefold()
        resources = []
        if "linux" in normalized:
            resources.append(LearningResource(
                topic=topic, title="The Linux command line for beginners",
                url="https://documentation.ubuntu.com/desktop/en/latest/tutorial/the-linux-command-line-for-beginners/",
                source="Ubuntu Documentation", level="beginner",
                reason="Official practical introduction to files, commands, pipes, and administrator boundaries.",
            ))
        if any(term in normalized for term in ("office", "excel", "word", "powerpoint")):
            resources.append(LearningResource(
                topic=topic, title="Office and Microsoft 365 training resources",
                url="https://support.microsoft.com/en-us/office/o365-itpro/train-your-users-on-office-and-microsoft-365",
                source="Microsoft Support", level="beginner",
                reason="Official training entry point for Excel, Word, PowerPoint, and Microsoft 365.",
            ))
        return resources[:limit]


class DatabaseCatalogResourceSearch:
    def __init__(self, repository: LearningResourceRepository = learning_resource_repository) -> None:
        self.repository = repository

    async def search(self, topic: str, *, limit: int = 2) -> list[LearningResource]:
        return self.repository.search(topic, limit=limit)


class CatalogFirstResourceSearch:
    def __init__(
        self,
        catalog: LearningResourceSearch,
        remote: LearningResourceSearch | None = None,
    ) -> None:
        self.catalog = catalog
        self.remote = remote

    async def search(self, topic: str, *, limit: int = 2) -> list[LearningResource]:
        curated = await self.catalog.search(topic, limit=limit)
        # A curated hit is already sufficient. Remote search is discovery for
        # uncovered topics, not a requirement that can invalidate local results.
        if curated or self.remote is None:
            return curated
        discovered = await self.remote.search(topic, limit=limit - len(curated))
        seen = {item.url for item in curated}
        return curated + [item for item in discovered if item.url not in seen][:limit - len(curated)]


def resolve_learning_resource_search() -> tuple[LearningResourceSearch, str]:
    catalog = DatabaseCatalogResourceSearch()
    url = os.getenv("JOBAGENT_LEARNING_MCP_URL", "").strip()
    if url and urlparse(url).scheme in {"http", "https"}:
        remote = MCPStreamableHTTPResourceSearch(
                url=url,
                tool_name=os.getenv("JOBAGENT_LEARNING_MCP_TOOL", "search").strip() or "search",
                query_argument=os.getenv("JOBAGENT_LEARNING_MCP_QUERY_ARGUMENT", "query").strip() or "query",
            )
        return CatalogFirstResourceSearch(catalog, remote), "catalog_mcp"
    return CatalogFirstResourceSearch(catalog), "curated_catalog"


def _resources_from_payloads(topic: str, payloads: list[object], *, limit: int) -> list[LearningResource]:
    candidates: list[dict[str, object]] = []
    for payload in payloads:
        if isinstance(payload, list):
            candidates.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            for key in ("results", "items", "resources"):
                value = payload.get(key)
                if isinstance(value, list):
                    candidates.extend(item for item in value if isinstance(item, dict))
    resources = []
    for item in candidates:
        url = str(item.get("url") or item.get("link") or "").strip()
        if urlparse(url).scheme not in {"http", "https"}:
            continue
        resources.append(LearningResource(
            topic=topic,
            title=str(item.get("title") or topic).strip(),
            url=url,
            source=str(item.get("source") or urlparse(url).netloc).strip(),
            level="review",
            reason=str(item.get("snippet") or item.get("description") or "Relevant tutorial returned by the configured MCP search tool.").strip(),
        ))
        if len(resources) >= limit:
            break
    return resources


def resource_error_summary(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        parts = [resource_error_summary(item) for item in error.exceptions]
        return " | ".join(dict.fromkeys(parts))[:500]
    message = (str(error) or type(error).__name__).strip().replace("\n", " ")
    return f"{type(error).__name__}: {message}"[:500]
