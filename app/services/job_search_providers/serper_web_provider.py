from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlencode, urlparse

from app.services.job_search_providers.base import JobSearchProviderError, RawJobCandidate

SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_PREVIEW_URL = "https://www.google.com/search"
SERPER_USER_AGENT = "JobAgent/0.1 serper-web-provider"
DEFAULT_SERPER_NUM_RESULTS = 10


def build_serper_preview_search_url(
    query: str,
    *,
    location: str | None = None,
    search_sites: list[str] | None = None,
) -> str:
    return f"{SERPER_PREVIEW_URL}?{urlencode({'q': build_serper_query(query, location=location, search_sites=search_sites)})}"


def build_serper_query(
    query: str,
    *,
    location: str | None = None,
    search_sites: list[str] | None = None,
) -> str:
    parts: list[str] = []
    site_filter = _site_filter(search_sites or [])
    if site_filter:
        parts.append(site_filter)
    if query.strip():
        parts.append(query.strip())
    if location and location.strip():
        parts.append(location.strip())
    return " ".join(parts).strip()


def configured_serper_search_sites() -> list[str]:
    raw = os.getenv("JOBAGENT_WEB_SEARCH_SITES", "")
    return _clean_sites(raw.split(","))


class SerperWebSearchProvider:
    provider_name = "serper_web"
    provider_kind = "search_engine"
    detail_strategy = "search_result_snippet_only"
    search_url = SERPER_SEARCH_URL

    def __init__(
        self,
        *,
        api_key: str | None = None,
        search_sites: list[str] | None = None,
        fetcher: Callable[[urllib.request.Request], bytes] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SERPER_API_KEY") or os.getenv("JOBAGENT_SERPER_API_KEY")
        self.search_sites = _clean_sites(search_sites or configured_serper_search_sites())
        self.fetcher = fetcher or _fetch_request_bytes

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        if not self.api_key:
            raise JobSearchProviderError("Serper API key is not configured.")

        serper_query = build_serper_query(query, location=location, search_sites=self.search_sites)
        payload = {
            "q": serper_query,
            "num": max(1, min(limit, DEFAULT_SERPER_NUM_RESULTS)),
        }
        request = urllib.request.Request(
            SERPER_SEARCH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": self.api_key,
                "User-Agent": SERPER_USER_AGENT,
            },
            method="POST",
        )

        try:
            body = self.fetcher(request)
        except urllib.error.HTTPError as exc:
            raise JobSearchProviderError(f"Serper request failed with HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise JobSearchProviderError(f"Serper request failed: {exc.reason}.") from exc
        except TimeoutError as exc:
            raise JobSearchProviderError("Serper request timed out.") from exc

        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise JobSearchProviderError("Serper returned invalid JSON.") from exc

        candidates: list[RawJobCandidate] = []
        for index, item in enumerate(data.get("organic", []) or []):
            if not isinstance(item, dict):
                continue
            title = _clean_text(str(item.get("title") or ""))
            link = _clean_text(str(item.get("link") or ""))
            snippet = _clean_text(str(item.get("snippet") or ""))
            if not title or not link:
                continue
            display_link = _clean_text(str(item.get("displayLink") or ""))
            candidates.append(
                RawJobCandidate(
                    title=title,
                    company=_domain_label(display_link or link),
                    location=location,
                    source_url=link,
                    source_provider=self.provider_name,
                    snippet=snippet or title,
                    raw_description=snippet or title,
                    discovery_query=serper_query,
                    discovery_rank=index + 1,
                    detail_status="search_result_snippet_only",
                    provider_warnings=["Search engine snippet only; detail page was not fetched."],
                )
            )
            if len(candidates) >= limit:
                break
        return candidates


def _fetch_request_bytes(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=20.0) as response:
        return response.read()


def _site_filter(search_sites: list[str]) -> str:
    sites = _clean_sites(search_sites)
    if not sites:
        return ""
    if len(sites) == 1:
        return f"site:{sites[0]}"
    return "(" + " OR ".join(f"site:{site}" for site in sites) + ")"


def _clean_sites(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip().lower()
        if not item:
            continue
        item = item.removeprefix("https://").removeprefix("http://").rstrip("/")
        key = item.removeprefix("www.")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _domain_label(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = parsed.netloc or parsed.path
    host = host.removeprefix("www.")
    return host or None


def _clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()
