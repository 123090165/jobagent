from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from typing import Callable, Protocol
from urllib.parse import urlparse

from app.services.job_search_providers.base import JobSearchProviderError, RawJobCandidate

FetchText = Callable[[str], str]


class JobSiteAdapter(Protocol):
    name: str
    allowed_domains: list[str]

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        ...

    def fetch_job_detail(self, candidate: RawJobCandidate) -> RawJobCandidate:
        ...


class BaseHTTPJobSiteAdapter:
    name = "base"
    allowed_domains: list[str] = []

    def __init__(
        self,
        *,
        listing_urls: list[str],
        fetcher: FetchText | None = None,
        listing_pages: dict[str, str] | None = None,
        detail_pages: dict[str, str] | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.listing_urls = listing_urls
        self.fetcher = fetcher
        self.listing_pages = listing_pages or {}
        self.detail_pages = detail_pages or {}
        self.timeout_seconds = timeout_seconds

    def _fetch_listing_html(self, url: str) -> str:
        if url in self.listing_pages:
            return self.listing_pages[url]
        return self._fetch_text(url)

    def _fetch_detail_html(self, url: str) -> str:
        if url in self.detail_pages:
            return self.detail_pages[url]
        return self._fetch_text(url)

    def _fetch_text(self, url: str) -> str:
        if not _is_allowed_url(url, self.allowed_domains):
            raise JobSearchProviderError(f"{self.name} adapter blocked non-allowlisted URL: {url}")
        if self.fetcher is not None:
            return self.fetcher(url)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "JobAgent/0.1 curated-crawler"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise JobSearchProviderError(f"{self.name} adapter HTTP error {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise JobSearchProviderError(f"{self.name} adapter request failed for {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise JobSearchProviderError(f"{self.name} adapter timed out for {url}") from exc

    def _matches(self, candidate: RawJobCandidate, *, query: str, location: str | None) -> bool:
        query_terms = _tokenize(query)
        haystack = " ".join(
            filter(
                None,
                [
                    candidate.title or "",
                    candidate.company or "",
                    candidate.location or "",
                    candidate.snippet or "",
                    candidate.raw_description or "",
                ],
            )
        ).lower()
        if query_terms and not any(term in haystack for term in query_terms):
            return False
        if location:
            location_terms = _tokenize(location)
            if location_terms and not any(term in haystack for term in location_terms):
                return False
        return True


def strip_html_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    normalized = html.unescape(without_tags)
    return re.sub(r"\s+", " ", normalized).strip()


def extract_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return strip_html_text(match.group(1))
    return None


def normalize_url(url: str, *, base_url: str | None = None) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if base_url is None:
        return url
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}{url}"


def derive_company_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 1:
        return parts[0].replace("-", " ").title()
    host = parsed.netloc.replace("www.", "")
    return host.split(".")[0].replace("-", " ").title()


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [part for part in re.split(r"[^a-z0-9]+", text.lower()) if part]


def _is_allowed_url(url: str, allowed_domains: list[str]) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)
