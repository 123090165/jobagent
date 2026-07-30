"""回归验证learning search mcp server的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import asyncio

import httpx

from mcp_servers.learning_search import server


def test_normalize_results_filters_invalid_and_duplicate_urls() -> None:
    results = server._normalize_results({
        "results": [
            {"title": "Linux tutorial", "url": "https://docs.example.com/linux", "content": "Start here"},
            {"title": "Duplicate", "url": "https://docs.example.com/linux"},
            {"title": "Local file", "url": "file:///tmp/tutorial"},
            {"title": "", "url": "https://example.org/missing-title"},
            {"title": "Office tutorial", "url": "https://www.example.org/office"},
        ]
    }, limit=5)

    assert results == [
        {
            "title": "Linux tutorial",
            "url": "https://docs.example.com/linux",
            "snippet": "Start here",
            "source": "docs.example.com",
        },
        {
            "title": "Office tutorial",
            "url": "https://www.example.org/office",
            "snippet": "",
            "source": "example.org",
        },
    ]


def test_search_calls_tavily_with_bounded_results(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={
            "results": [{
                "title": "Python documentation",
                "url": "https://docs.python.org/3/tutorial/",
                "content": "Official Python tutorial",
            }]
        })

    original_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(server.httpx, "AsyncClient", client_factory)

    result = asyncio.run(server.search("Python beginner tutorial", max_results=99))

    assert captured["authorization"] == "Bearer test-key"
    assert '"max_results":8' in str(captured["body"]).replace(" ", "")
    assert '"youtube.com"' in str(captured["body"])
    assert result["results"][0]["source"] == "docs.python.org"


def test_search_requires_tavily_key(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    try:
        asyncio.run(server.search("Linux tutorial"))
    except RuntimeError as exc:
        assert str(exc) == "TAVILY_API_KEY is not configured"
    else:
        raise AssertionError("search should reject missing Tavily credentials")
