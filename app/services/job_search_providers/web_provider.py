from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from app.services.job_search_providers.base import (
    JobSearchProviderError,
    RawJobCandidate,
)


class WebSearchProvider:
    provider_name = "tavily"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = (base_url or os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        if not self.api_key:
            raise JobSearchProviderError("Tavily provider is not configured. Set TAVILY_API_KEY first.")

        search_query = query.strip()
        if location:
            search_query = f"{search_query} {location}"
        payload = {
            "api_key": self.api_key,
            "query": f"{search_query} job opening career site",
            "topic": "general",
            "search_depth": "advanced",
            "max_results": max(1, min(limit, 20)),
            "include_answer": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise JobSearchProviderError(f"Tavily HTTP error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise JobSearchProviderError(f"Tavily request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise JobSearchProviderError("Tavily request timed out") from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise JobSearchProviderError("Tavily response is not valid JSON") from exc

        results = decoded.get("results", [])
        if not isinstance(results, list):
            raise JobSearchProviderError("Tavily response does not contain a results list")

        return [self._to_candidate(item, location) for item in results[:limit] if isinstance(item, dict)]

    def _to_candidate(self, item: dict[str, Any], location: str | None) -> RawJobCandidate:
        title = _coerce_text(item.get("title")) or "Unknown Role"
        snippet = _coerce_text(item.get("content")) or _coerce_text(item.get("snippet")) or ""
        if not snippet:
            snippet = f"Search result for {title}"
        return RawJobCandidate(
            title=title,
            company=_infer_company(item),
            location=location,
            source_url=_coerce_text(item.get("url")),
            source_provider=self.provider_name,
            snippet=snippet,
            raw_description=snippet,
        )


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _infer_company(item: dict[str, Any]) -> str | None:
    for key in ("author", "company", "domain"):
        text = _coerce_text(item.get(key))
        if text:
            return text
    url = _coerce_text(item.get("url"))
    if not url:
        return None
    host = url.split("//")[-1].split("/")[0]
    return host.replace("www.", "")
