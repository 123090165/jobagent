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
FULL_JD_RERANK_BONUS = 2.0
PARTIAL_JD_RERANK_BONUS = 0.75
EXTERNAL_LINK_ONLY_RERANK_BONUS = -0.5
SNIPPET_ONLY_RERANK_BONUS = -1.0
INVALID_RERANK_BONUS = -2.0


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

        details: list[RawJobDetail] = []
        warnings: list[str] = []
        detail_failed = 0
        for index, item in enumerate(candidate_items):
            try:
                detail_html = fetch_public_html(item.detail_url, timeout_seconds=self._timeout_seconds)
                detail = self._parser.parse_detail(detail_html, item)
            except Exception:
                detail_failed += 1
                warnings.append(f"detail_fetch_or_parse_failed:{item.detail_url}")
                if index < len(candidate_items) - 1 and self._detail_request_sleep_seconds > 0:
                    time.sleep(self._detail_request_sleep_seconds)
                continue

            if self._save_to_local_db:
                save_public_job_post(detail, database_path=self._database_path)

            details.append(detail)

            if index < len(candidate_items) - 1 and self._detail_request_sleep_seconds > 0:
                time.sleep(self._detail_request_sleep_seconds)

        ranked_details = _rerank_details(details, query)
        selected_details = ranked_details[: max(1, int(limit))]
        results = [_detail_to_search_result(detail) for detail in selected_details]

        metadata = {
            "list_items_found": len(list_items),
            "detail_candidates": len(candidate_items),
            "detail_success": len(details),
            "detail_failed": detail_failed,
            "returned_count": len(results),
            "rerank_applied": True,
        }
        return SearchResultSet(
            query=query,
            provider=self.name,
            items=results,
            warnings=warnings,
            metadata=metadata,
        )


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
    query_terms = _build_query_terms(query)

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


def _rerank_details(details: list[RawJobDetail], query: str) -> list[RawJobDetail]:
    return sorted(
        details,
        key=lambda detail: (
            _build_detail_score(detail, query),
            float(detail.confidence),
            detail.list_item.external_id,
        ),
        reverse=True,
    )


def _build_detail_score(detail: RawJobDetail, query: str) -> float:
    query_terms = _build_query_terms(query)
    if not query_terms:
        return _quality_bonus(detail) + float(detail.confidence)

    item = detail.list_item
    title = (item.title or "").lower()
    company = (item.company or "").lower()
    location = (item.location or "").lower()
    job_type = (item.job_type or "").lower()
    education = (item.education or "").lower()
    jd_text = (detail.jd_text or "").lower()
    responsibilities = "\n".join(_extract_section_lines(detail.jd_text or "", RESPONSIBILITY_HEADINGS)).lower()
    requirements = "\n".join(_extract_section_lines(detail.jd_text or "", REQUIREMENT_HEADINGS)).lower()
    skills = "\n".join(_extract_skills(detail.jd_text or "")).lower()

    score = 0.0
    for term in query_terms:
        if term in title:
            score += 5.0
        score += min(jd_text.count(term), 5) * 2.0
        if term in company:
            score += 1.0
        if term in location:
            score += 1.0
        if term in job_type:
            score += 1.0
        if term in education:
            score += 1.0
        if term in responsibilities:
            score += 1.5
        if term in requirements:
            score += 1.5
        if term in skills:
            score += 1.5

    return score + _quality_bonus(detail) + float(detail.confidence)


def _quality_bonus(detail: RawJobDetail) -> float:
    if detail.quality_label == "full_jd":
        return FULL_JD_RERANK_BONUS
    if detail.quality_label == "partial_jd":
        return PARTIAL_JD_RERANK_BONUS
    if detail.quality_label == "external_link_only":
        return EXTERNAL_LINK_ONLY_RERANK_BONUS
    if detail.quality_label == "snippet_only":
        return SNIPPET_ONLY_RERANK_BONUS
    if detail.quality_label == "invalid":
        return INVALID_RERANK_BONUS
    return 0.0


def _build_query_terms(query: str) -> list[str]:
    return [term.strip().lower() for term in str(query or "").split() if term.strip()] or (
        [str(query).strip().lower()] if str(query or "").strip() else []
    )


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
