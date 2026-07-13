from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

from app.config.env_loader import load_local_env

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_RESULTS = 8
LOW_SIGNAL_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "x.com",
]

load_local_env()

mcp = FastMCP(
    "jobagent-learning-search",
    instructions=(
        "Search for a small number of practical learning resources. "
        "Results are web references, not evidence of candidate ability."
    ),
    host=os.getenv("JOBAGENT_LEARNING_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("JOBAGENT_LEARNING_MCP_PORT", "8001")),
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def search(query: str, max_results: int = 5) -> dict[str, list[dict[str, str]]]:
    """Search Tavily and return bounded HTTP(S) learning resources."""
    normalized_query = query.strip()
    if not normalized_query:
        return {"results": []}

    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    result_limit = max(1, min(max_results, MAX_RESULTS))
    payload = {
        "query": normalized_query,
        "search_depth": "basic",
        "topic": "general",
        "max_results": result_limit,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "exclude_domains": LOW_SIGNAL_DOMAINS,
    }
    timeout = float(os.getenv("TAVILY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.post(
            TAVILY_SEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
    return {"results": _normalize_results(response.json(), limit=result_limit)}


def _normalize_results(payload: object, *, limit: int) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return []

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        url = _text(item.get("url"))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen_urls:
            continue
        title = _text(item.get("title"))
        if not title:
            continue
        results.append({
            "title": title,
            "url": url,
            "snippet": _text(item.get("content")),
            "source": parsed.netloc.removeprefix("www."),
        })
        seen_urls.add(url)
        if len(results) >= limit:
            break
    return results


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
