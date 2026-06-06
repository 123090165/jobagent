from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.search import SearchResultItem, SearchResultSet
from app.services.live_job.base import JobSiteParser, RawJobDetail, RawJobListItem
from app.services.live_job.fetcher import DEFAULT_TIMEOUT_SECONDS, fetch_public_html
from app.services.live_job.parsers.cuhksz import CUHKSZParser, DEFAULT_CUHKSZ_LIST_URL
from app.services.public_job_storage_service import save_public_job_post
from app.services.search_providers.local_public_job_provider import (
    REQUIREMENT_HEADINGS,
    RESPONSIBILITY_HEADINGS,
    _extract_section_lines,
    _extract_skills,
)
from app.services.search_providers.base import SearchProvider

DEFAULT_DETAIL_REQUEST_SLEEP_SECONDS = 0.2
DEFAULT_DETAIL_CANDIDATE_MULTIPLIER = 2
MAX_DETAIL_CANDIDATES = 10


class CUHKSZLiveProvider(SearchProvider):
    name = "cuhksz_live"

    def __init__(
        self,
        list_url: str = DEFAULT_CUHKSZ_LIST_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        save_to_local_db: bool = False,
        database_path: str | Path | None = None,
        detail_request_sleep_seconds: float = DEFAULT_DETAIL_REQUEST_SLEEP_SECONDS,
        parser: JobSiteParser | None = None,
    ) -> None:
        self._list_url = list_url
        self._timeout_seconds = timeout_seconds
        self._save_to_local_db = save_to_local_db
        self._database_path = database_path
        self._detail_request_sleep_seconds = max(0.0, float(detail_request_sleep_seconds))
        self._parser = parser or CUHKSZParser()

    def search_jobs(self, query: str, limit: int = 5) -> SearchResultSet:
        list_html = fetch_public_html(self._list_url, timeout_seconds=self._timeout_seconds)
        list_items = self._parser.parse_list(list_html, self._list_url)
        candidate_items = _select_detail_candidates(list_items, query, limit)

        results: list[SearchResultItem] = []
        for index, item in enumerate(candidate_items):
            try:
                detail_html = fetch_public_html(item.detail_url, timeout_seconds=self._timeout_seconds)
                detail = self._parser.parse_detail(detail_html, item)
            except Exception:
                if index < len(candidate_items) - 1 and self._detail_request_sleep_seconds > 0:
                    time.sleep(self._detail_request_sleep_seconds)
                continue

            if self._save_to_local_db:
                save_public_job_post(detail, database_path=self._database_path)

            results.append(_detail_to_search_result(detail))
            if len(results) >= limit:
                break

            if index < len(candidate_items) - 1 and self._detail_request_sleep_seconds > 0:
                time.sleep(self._detail_request_sleep_seconds)

        return SearchResultSet(query=query, provider=self.name, items=results)


def _select_detail_candidates(
    list_items: list[RawJobListItem],
    query: str,
    limit: int,
) -> list[RawJobListItem]:
    normalized_limit = max(1, int(limit))
    ranked_items = sorted(
        list_items,
        key=lambda item: _build_list_item_score(item, query),
        reverse=True,
    )
    candidate_count = min(
        max(normalized_limit * DEFAULT_DETAIL_CANDIDATE_MULTIPLIER, normalized_limit),
        MAX_DETAIL_CANDIDATES,
    )
    return ranked_items[:candidate_count]


def _build_list_item_score(item: RawJobListItem, query: str) -> float:
    query_terms = [term.strip().lower() for term in str(query or "").split() if term.strip()]
    if not query_terms and str(query or "").strip():
        query_terms = [str(query).strip().lower()]

    title = (item.title or "").lower()
    haystacks = [
        title,
        (item.company or "").lower(),
        (item.location or "").lower(),
        (item.job_type or "").lower(),
        (item.education or "").lower(),
    ]
    searchable_text = "\n".join(haystacks)

    score = 0.0
    for term in query_terms:
        occurrences = searchable_text.count(term)
        if not occurrences:
            continue
        score += min(occurrences, 3)
        if term in title:
            score += 1.5

    return score


def _detail_to_search_result(detail: RawJobDetail) -> SearchResultItem:
    item = detail.list_item
    jd_text = detail.jd_text.strip()
    return SearchResultItem(
        title=item.title,
        company=item.company or "",
        location=item.location or "",
        url=item.detail_url,
        snippet=detail.snippet,
        source=item.source,
        retrieved_at=datetime.now(timezone.utc),
        responsibilities=_extract_section_lines(jd_text, RESPONSIBILITY_HEADINGS),
        requirements=_extract_section_lines(jd_text, REQUIREMENT_HEADINGS),
        skills=_extract_skills(jd_text),
        jd_text=jd_text or None,
        is_full_jd=detail.is_full_jd,
        confidence=detail.confidence,
        quality_label=detail.quality_label,
        warnings=list(detail.warnings),
        external_links=list(detail.external_links),
    )
