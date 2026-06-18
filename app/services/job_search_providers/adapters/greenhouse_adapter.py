from __future__ import annotations

import re

from app.services.job_search_providers.adapters.base import (
    BaseHTTPJobSiteAdapter,
    derive_company_from_url,
    extract_first,
    normalize_url,
    strip_html_text,
)
from app.services.job_search_providers.base import RawJobCandidate

DEFAULT_GREENHOUSE_LISTING_URLS = [
    "https://boards.greenhouse.io/openai",
]


class GreenhouseAdapter(BaseHTTPJobSiteAdapter):
    name = "greenhouse"
    allowed_domains = ["boards.greenhouse.io"]

    def __init__(
        self,
        *,
        listing_urls: list[str] | None = None,
        fetcher=None,
        listing_pages: dict[str, str] | None = None,
        detail_pages: dict[str, str] | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        super().__init__(
            listing_urls=listing_urls or DEFAULT_GREENHOUSE_LISTING_URLS,
            fetcher=fetcher,
            listing_pages=listing_pages,
            detail_pages=detail_pages,
            timeout_seconds=timeout_seconds,
        )

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        items: list[RawJobCandidate] = []
        for listing_url in self.listing_urls:
            html = self._fetch_listing_html(listing_url)
            for candidate in self._parse_listing_html(html, listing_url):
                if self._matches(candidate, query=query, location=location):
                    items.append(candidate)
                if len(items) >= limit:
                    return items[:limit]
        return items[:limit]

    def fetch_job_detail(self, candidate: RawJobCandidate) -> RawJobCandidate:
        if not candidate.source_url:
            return candidate
        html = self._fetch_detail_html(candidate.source_url)
        description = extract_first(
            [
                r'<div[^>]+id="content"[^>]*>(.*?)</div>',
                r'<section[^>]+class="content"[^>]*>(.*?)</section>',
                r'<div[^>]+class="content"[^>]*>(.*?)</div>',
            ],
            html,
        )
        if not description:
            return candidate.model_copy(
                update={
                    "provider_warnings": candidate.provider_warnings + ["Job detail page did not expose a parseable description."],
                }
            )
        snippet = description[:280]
        return candidate.model_copy(update={"raw_description": description, "snippet": snippet})

    def _parse_listing_html(self, html: str, listing_url: str) -> list[RawJobCandidate]:
        candidates: list[RawJobCandidate] = []
        company = derive_company_from_url(listing_url)
        anchor_pattern = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
        for href, body in anchor_pattern.findall(html):
            title = extract_first(
                [
                    r'data-qa="job-name"[^>]*>(.*?)</',
                    r'class="[^"]*opening--title[^"]*"[^>]*>(.*?)</',
                    r"<h\d[^>]*>(.*?)</h\d>",
                ],
                body,
            )
            location = extract_first(
                [
                    r'data-qa="job-location"[^>]*>(.*?)</',
                    r'class="[^"]*location[^"]*"[^>]*>(.*?)</',
                ],
                body,
            )
            snippet = strip_html_text(body)
            if not title:
                continue
            candidates.append(
                RawJobCandidate(
                    title=title,
                    company=company,
                    location=location,
                    source_url=normalize_url(href, base_url=listing_url),
                    source_provider="curated_crawler",
                    snippet=snippet,
                    raw_description=None,
                )
            )
        return candidates
