from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.schemas.search import SearchResultItem
from app.services.jd_quality_service import evaluate_jd_quality

DEFAULT_CUHKSZ_TIMEOUT_SECONDS = 15
MAX_PUBLIC_HTML_BYTES = 3 * 1024 * 1024
USER_AGENT = "JobAgent/0.1 (+https://github.com/123090165/jobagent)"

DETAIL_BODY_SELECTORS = [
    ".subcontent",
    ".container",
    ".job_detail",
    ".job_view",
    ".content",
    "body",
]

NAVIGATION_TERMS = [
    "登录",
    "注册",
    "关于我们",
    "招聘信息",
    "就业指导",
    "返回主站",
    "香港中文大学（深圳）© 版权所有",
]

def fetch_public_html(url: str, timeout_seconds: int = DEFAULT_CUHKSZ_TIMEOUT_SECONDS) -> str:
    normalized_url = _validate_http_url(url)
    response = requests.get(
        normalized_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
        timeout=timeout_seconds,
        stream=True,
    )
    try:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_PUBLIC_HTML_BYTES:
            raise ValueError("Public HTML response is too large")

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_PUBLIC_HTML_BYTES:
                raise ValueError("Public HTML response is too large")
            chunks.append(chunk)
        body = b"".join(chunks)
    finally:
        response.close()

    encoding = response.encoding or response.apparent_encoding or "utf-8"
    return body.decode(encoding, errors="replace")


def parse_cuhksz_job_list(html: str, base_url: str) -> list[CUHKSZJobListItem]:
    soup = BeautifulSoup(html, "html.parser")
    list_nodes = soup.select(".sousuo_list ul > li") or soup.select(".sousuo_list li")
    items: list[CUHKSZJobListItem] = []

    for node in list_nodes:
        company_node = node.select_one(".sousuo_list_com a")
        title_node = node.select_one(".sousuo_list_xx a.f18")
        if title_node is None:
            continue

        title = _clean_inline_text(title_node.get_text(" ", strip=True))
        href = str(title_node.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        external_id = _extract_external_id(href or detail_url)
        if not title or not detail_url or not external_id:
            continue

        meta_node = node.select_one(".sousuo_list_xx .mt10.mb10")
        location, job_type, education = _parse_meta_text(
            meta_node.get_text(" ", strip=True) if meta_node else ""
        )
        published_at, deadline = _parse_time_text(
            node.select_one(".sousuo_list_time").get_text(" ", strip=True)
            if node.select_one(".sousuo_list_time")
            else ""
        )

        items.append(
            CUHKSZJobListItem(
                external_id=external_id,
                title=title,
                company=_clean_inline_text(company_node.get_text(" ", strip=True))
                if company_node
                else None,
                location=location,
                job_type=job_type,
                education=education,
                published_at=published_at,
                deadline=deadline,
                detail_url=detail_url,
            )
        )

    return items


def fetch_cuhksz_job_detail(
    detail_url: str,
    timeout_seconds: int = DEFAULT_CUHKSZ_TIMEOUT_SECONDS,
) -> str:
    return fetch_public_html(detail_url, timeout_seconds=timeout_seconds)


def extract_cuhksz_jd_text(detail_html: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup.select("script,style,noscript,nav,footer,header"):
        node.decompose()

    fallback_text = ""
    for selector in DETAIL_BODY_SELECTORS:
        body_node = soup.select_one(selector)
        if body_node is None:
            continue
        text = _clean_detail_text(body_node.get_text("\n", strip=True))
        if not fallback_text and text:
            fallback_text = text
        if len(text) >= 50 or selector == "body":
            if not text:
                warnings.append("jd_text_empty")
            return text, warnings

    if not fallback_text:
        warnings.append("jd_text_empty")
    return fallback_text, warnings


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
    extracted_text, extraction_warnings = extract_cuhksz_jd_text(detail_html)
    fallback_text = _build_fallback_text(list_item)
    jd_text = extracted_text.strip() or fallback_text
    quality_report = evaluate_jd_quality(
        jd_text,
        title=list_item.title,
        source_url=list_item.detail_url,
    )
    warnings = [*extraction_warnings, *quality_report.warnings]

    if not extracted_text.strip():
        warnings.append("jd_text_empty_fallback_used")

    snippet = (extracted_text.strip() or fallback_text)[:300].strip()
    return CUHKSZJobDetail(
        list_item=list_item,
        jd_text=jd_text,
        snippet=snippet,
        is_full_jd=quality_report.is_full_jd,
        confidence=quality_report.quality_score,
        quality_label=quality_report.quality_label,
        warnings=_dedupe_preserve_order(warnings),
        external_links=quality_report.external_links,
    )


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


def _validate_http_url(url: str) -> str:
    normalized_url = (url or "").strip()
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Public URL must use http or https")
    if not parsed.netloc:
        raise ValueError("Public URL is invalid")
    return normalized_url


def _extract_external_id(href: str) -> str:
    parsed_path = urlparse(href).path or href
    match = re.search(r"/job/view/id/([^/?#]+)", parsed_path)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:^|/)id/([^/?#]+)", parsed_path)
    return match.group(1).strip() if match else ""


def _parse_meta_text(meta_text: str) -> tuple[str | None, str | None, str | None]:
    text = _clean_inline_text(meta_text)
    if not text:
        return None, None, None
    parts = [part.strip() for part in re.split(r"\s*[|｜丨]\s*", text) if part.strip()]
    location = parts[0] if len(parts) >= 1 else None
    job_type = parts[1] if len(parts) >= 2 else None
    education = parts[2] if len(parts) >= 3 else None
    return location, job_type, education


def _parse_time_text(time_text: str) -> tuple[str | None, str | None]:
    dates = [_normalize_date(value) for value in re.findall(r"\d{4}-\d{1,2}-\d{1,2}", time_text)]
    published_at = dates[0] if len(dates) >= 1 else None
    deadline = dates[1] if len(dates) >= 2 else None
    return published_at, deadline


def _normalize_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _clean_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _clean_detail_text(text: str) -> str:
    normalized = (text or "").replace("\xa0", " ")
    lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = _clean_inline_text(raw_line)
        if not line:
            continue
        if _is_navigation_line(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _is_navigation_line(line: str) -> bool:
    if line in NAVIGATION_TERMS:
        return True
    return "版权所有" in line and "香港中文大学" in line


def _build_fallback_text(item: CUHKSZJobListItem) -> str:
    lines = [
        f"Title: {item.title}",
        f"Company: {item.company or ''}",
        f"Location: {item.location or ''}",
        f"Job Type: {item.job_type or ''}",
        f"Education: {item.education or ''}",
        f"Published At: {item.published_at or ''}",
        f"Deadline: {item.deadline or ''}",
        f"Source URL: {item.detail_url}",
    ]
    return "\n".join(line for line in lines if line.split(":", 1)[1].strip())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
