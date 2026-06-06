from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.schemas.search import SearchResultItem
from app.services.jd_quality_service import evaluate_jd_quality
from app.services.live_job.fetcher import (
    DEFAULT_MAX_PUBLIC_HTML_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    USER_AGENT,
    fetch_public_html as _fetch_public_html,
)
from app.services.live_job.parsers.cuhksz import (
    CUHKSZParser,
    DETAIL_BODY_SELECTORS,
    NAVIGATION_TERMS,
    extract_cuhksz_detail_text,
)
from app.services.live_job.base import RawJobDetail, RawJobListItem

DEFAULT_CUHKSZ_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
MAX_PUBLIC_HTML_BYTES = DEFAULT_MAX_PUBLIC_HTML_BYTES

_PARSER = CUHKSZParser()


def fetch_public_html(url: str, timeout_seconds: int = DEFAULT_CUHKSZ_TIMEOUT_SECONDS) -> str:
    return _fetch_public_html(url, timeout_seconds=timeout_seconds)


def parse_cuhksz_job_list(html: str, base_url: str) -> list[CUHKSZJobListItem]:
    return [_raw_item_to_cuhksz_item(item) for item in _PARSER.parse_list(html, base_url)]


def fetch_cuhksz_job_detail(
    detail_url: str,
    timeout_seconds: int = DEFAULT_CUHKSZ_TIMEOUT_SECONDS,
) -> str:
    return fetch_public_html(detail_url, timeout_seconds=timeout_seconds)


def extract_cuhksz_jd_text(detail_html: str) -> tuple[str, list[str]]:
    return extract_cuhksz_detail_text(detail_html)


def evaluate_cuhksz_jd_quality(jd_text: str) -> tuple[bool, float, list[str]]:
    report = evaluate_jd_quality(jd_text)
    warnings = [
        "jd_text_too_short" if warning == "jd_text_empty_or_too_short" else warning
        for warning in report.warnings
    ]
    return report.is_full_jd, report.quality_score, warnings


def build_cuhksz_job_detail(
    list_item: CUHKSZJobListItem,
    detail_html: str,
) -> CUHKSZJobDetail:
    raw_detail = _PARSER.parse_detail(detail_html, _cuhksz_item_to_raw_item(list_item))
    return _raw_detail_to_cuhksz_detail(raw_detail)


def convert_cuhksz_detail_to_search_result(detail: CUHKSZJobDetail) -> SearchResultItem:
    item = detail.list_item
    return SearchResultItem(
        title=item.title,
        company=item.company or "",
        location=item.location or "",
        url=item.detail_url,
        snippet=detail.snippet,
        source=item.source,
        retrieved_at=datetime.now(timezone.utc),
        responsibilities=[],
        requirements=[],
        skills=[],
        jd_text=detail.jd_text,
        is_full_jd=detail.is_full_jd,
        confidence=detail.confidence,
        quality_label=detail.quality_label,
        warnings=detail.warnings,
        external_links=detail.external_links,
    )


def _raw_item_to_cuhksz_item(item: RawJobListItem) -> CUHKSZJobListItem:
    return CUHKSZJobListItem(
        external_id=item.external_id,
        title=item.title,
        company=item.company,
        location=item.location,
        job_type=item.job_type,
        education=item.education,
        published_at=item.published_at,
        deadline=item.deadline,
        detail_url=item.detail_url,
        source=item.source,
    )


def _cuhksz_item_to_raw_item(item: CUHKSZJobListItem) -> RawJobListItem:
    return RawJobListItem(
        source=item.source,
        external_id=item.external_id,
        title=item.title,
        company=item.company,
        location=item.location,
        job_type=item.job_type,
        education=item.education,
        published_at=item.published_at,
        deadline=item.deadline,
        detail_url=item.detail_url,
    )


def _raw_detail_to_cuhksz_detail(detail: RawJobDetail) -> CUHKSZJobDetail:
    return CUHKSZJobDetail(
        list_item=_raw_item_to_cuhksz_item(detail.list_item),
        jd_text=detail.jd_text,
        snippet=detail.snippet,
        is_full_jd=detail.is_full_jd,
        confidence=detail.confidence,
        quality_label=detail.quality_label or "invalid",
        extraction_method=detail.extraction_method or "cuhksz_html",
        warnings=list(detail.warnings),
        external_links=list(detail.external_links),
    )
