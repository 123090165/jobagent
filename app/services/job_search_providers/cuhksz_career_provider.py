from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections.abc import Callable

from bs4 import BeautifulSoup

from app.services.cuhksz_career_service import extract_cuhksz_jd_text, parse_cuhksz_job_list
from app.services.job_search_providers.base import JobSearchProviderError, RawJobCandidate

CUHKSZ_CAREER_BASE_URL = "https://career.cuhk.edu.cn"
CUHKSZ_CAREER_SEARCH_URL = "https://career.cuhk.edu.cn/job/search"
CUHKSZ_CAREER_ALLOWED_DOMAINS = ["career.cuhk.edu.cn"]
CUHKSZ_CAREER_USER_AGENT = "JobAgent/0.1 cuhksz-career-provider"


class CUHKSZCareerProvider:
    provider_name = "cuhksz_career"
    base_url = CUHKSZ_CAREER_BASE_URL
    search_url = CUHKSZ_CAREER_SEARCH_URL
    allowed_domains = CUHKSZ_CAREER_ALLOWED_DOMAINS

    def __init__(
        self,
        *,
        fetcher: Callable[[str], str] | None = None,
        list_page_html: str | None = None,
        detail_pages: dict[str, str] | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.list_page_html = list_page_html
        self.detail_pages = detail_pages or {}

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        list_html = self.list_page_html if self.list_page_html is not None else self._fetch(self.search_url)
        list_items = parse_cuhksz_job_list(list_html, self.search_url)
        query_terms = _tokenize(query)
        location_terms = _tokenize(location)

        candidates: list[RawJobCandidate] = []
        for item in list_items:
            snippet_lines = [
                part
                for part in [
                    item.company,
                    item.location,
                    item.job_type,
                    item.education,
                    _format_dates(item.published_at, item.deadline),
                ]
                if part
            ]
            candidate = RawJobCandidate(
                title=item.title,
                company=item.company,
                location=item.location,
                source_url=item.detail_url,
                source_provider=self.provider_name,
                snippet=" | ".join(snippet_lines) or item.title,
                raw_description=None,
            )
            if not _matches(candidate, query_terms=query_terms, location_terms=location_terms):
                continue
            candidates.append(self.fetch_job_detail(candidate))
            if len(candidates) >= limit:
                break
        return candidates[:limit]

    def fetch_job_detail(self, candidate: RawJobCandidate) -> RawJobCandidate:
        if not candidate.source_url:
            return candidate.model_copy(
                update={
                    "provider_warnings": candidate.provider_warnings + ["Missing CUHKSZ detail URL."],
                }
            )

        try:
            detail_html = self.detail_pages.get(candidate.source_url)
            if detail_html is None:
                detail_html = self._fetch(candidate.source_url)
            fields = _parse_detail_fields(detail_html)
        except Exception as exc:
            return candidate.model_copy(
                update={
                    "provider_warnings": candidate.provider_warnings + [f"Detail fetch failed: {type(exc).__name__}."],
                }
            )

        raw_description = _build_raw_description(fields)
        detail_snippet = (fields["job_description"] or raw_description or "").strip()
        if candidate.snippet and detail_snippet:
            snippet = f"{candidate.snippet} | {detail_snippet}"[:320].strip()
        else:
            snippet = (detail_snippet or candidate.snippet or "")[:320].strip()
        return candidate.model_copy(
            update={
                "title": fields["title"] or candidate.title,
                "company": fields["company"] or candidate.company,
                "location": fields["location"] or candidate.location,
                "snippet": snippet or candidate.snippet,
                "raw_description": raw_description or candidate.raw_description,
            }
        )

    def _fetch(self, url: str) -> str:
        if self.fetcher is not None:
            return self.fetcher(url)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": CUHKSZ_CAREER_USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20.0) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise JobSearchProviderError(f"CUHKSZ request failed with HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise JobSearchProviderError(f"CUHKSZ request failed for {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise JobSearchProviderError(f"CUHKSZ request timed out for {url}") from exc


def _parse_detail_fields(detail_html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup.select("script,style,noscript"):
        node.decompose()

    title = _first_text(soup, ["h1", ".job_name", ".position_name"])
    company = _search_label(detail_html, ["鍏徃鍚嶇О", "浼佷笟鍚嶇О"])
    location = _search_label(detail_html, ["宸ヤ綔鍦扮偣", "鍦扮偣"])
    employment_type = _search_label(detail_html, ["宸ヤ綔鎬ц川", "鑱屼綅鎬ц川"])
    category = _search_label(detail_html, ["鑱屼綅绫诲埆", "宀椾綅绫诲埆"])
    headcount = _search_label(detail_html, ["鎷涜仒浜烘暟", "浜烘暟"])
    salary = _search_label(detail_html, ["钖祫", "钖叕寰呴亣"])
    published_date = _search_label(detail_html, ["鍙戝竷鏃堕棿"])
    end_date = _search_label(detail_html, ["缁撴潫鏃堕棿", "鎴鏃堕棿"])
    extracted_jd_text, _warnings = extract_cuhksz_jd_text(detail_html)
    job_description = _extract_section(
        detail_html,
        ["宸ヤ綔鍐呭鎻忚堪", "宀椾綅鑱岃矗", "鑱屼綅鎻忚堪"],
    ) or extracted_jd_text
    company_intro = _extract_section(detail_html, ["浼佷笟绠€浠?", "鍏徃绠€浠?"])
    contact_info = _extract_section(detail_html, ["鑱旂郴鏂瑰紡", "鐢宠鏂瑰紡", "鎶曢€掓柟寮?"])

    return {
        "title": title,
        "company": company,
        "location": location,
        "employment_type": employment_type,
        "category": category,
        "headcount": headcount,
        "salary": salary,
        "published_date": published_date,
        "end_date": end_date,
        "job_description": job_description,
        "company_intro": company_intro,
        "contact_info": contact_info,
    }


def _build_raw_description(fields: dict[str, str | None]) -> str:
    lines = [
        _label_line("Title", fields["title"]),
        _label_line("Company", fields["company"]),
        _label_line("Location", fields["location"]),
        _label_line("Employment Type", fields["employment_type"]),
        _label_line("Category", fields["category"]),
        _label_line("Headcount", fields["headcount"]),
        _label_line("Salary", fields["salary"]),
        _label_line("Published Date", fields["published_date"]),
        _label_line("End Date", fields["end_date"]),
        _label_line("Job Description", fields["job_description"]),
        _label_line("Company Introduction", fields["company_intro"]),
        _label_line("Contact/Application Info", fields["contact_info"]),
    ]
    return "\n".join(line for line in lines if line)


def _label_line(label: str, value: str | None) -> str:
    text = (value or "").strip()
    return f"{label}: {text}" if text else ""


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = _clean_text(node.get_text(" ", strip=True))
            if text:
                return text
    return None


def _search_label(html: str, labels: list[str]) -> str | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:：]?\s*([^\n<]{{1,120}})", html, re.IGNORECASE)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return None


def _extract_section(html: str, labels: list[str]) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script,style,noscript"):
        node.decompose()

    headings = soup.find_all(["h1", "h2", "h3", "strong", "b"])
    for heading in headings:
        heading_text = _clean_text(heading.get_text(" ", strip=True))
        if not heading_text or not any(label in heading_text for label in labels):
            continue

        section_parts: list[str] = []
        parent = heading.parent
        if parent is not None and parent.name == "section":
            for child in parent.children:
                if child is heading:
                    continue
                text = _clean_text(getattr(child, "get_text", lambda *args, **kwargs: str(child))(" ", strip=True))
                if text:
                    section_parts.append(text)
        else:
            for sibling in heading.next_siblings:
                sibling_name = getattr(sibling, "name", None)
                if sibling_name in {"h1", "h2", "h3"}:
                    break
                text = _clean_text(getattr(sibling, "get_text", lambda *args, **kwargs: str(sibling))(" ", strip=True))
                if text:
                    section_parts.append(text)

        section_text = " ".join(section_parts).strip()
        if section_text:
            return section_text
    return None


def _clean_text(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    collapsed = re.sub(r"\s+", " ", no_tags.replace("\xa0", " ")).strip()
    return collapsed


def _format_dates(published_at: str | None, deadline: str | None) -> str | None:
    parts = []
    if published_at:
        parts.append(f"Published {published_at}")
    if deadline:
        parts.append(f"Ends {deadline}")
    return " | ".join(parts) if parts else None


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [part for part in re.split(r"[^a-z0-9\u4e00-\u9fff]+", text.lower()) if part]


def _matches(
    candidate: RawJobCandidate,
    *,
    query_terms: list[str],
    location_terms: list[str],
) -> bool:
    haystack = " ".join(
        filter(None, [candidate.title or "", candidate.company or "", candidate.location or "", candidate.snippet or ""])
    ).lower()
    if query_terms and not any(term in haystack for term in query_terms):
        return False
    if location_terms and not any(term in haystack for term in location_terms):
        return False
    return True
