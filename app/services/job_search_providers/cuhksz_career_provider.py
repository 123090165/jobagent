from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections.abc import Callable
from types import SimpleNamespace
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.job_search_providers.base import JobSearchProviderError, RawJobCandidate

CUHKSZ_CAREER_BASE_URL = "https://career.cuhk.edu.cn"
CUHKSZ_CAREER_SEARCH_URL = "https://career.cuhk.edu.cn/job/search"
CUHKSZ_CAREER_ALLOWED_DOMAINS = ["career.cuhk.edu.cn"]
CUHKSZ_CAREER_USER_AGENT = "JobAgent/0.1 cuhksz-career-provider"
NO_PROVIDER_MATCH_WARNING = "No provider-side keyword match; kept for downstream ranking."
CUHKSZ_TITLE_TYPE_KEYWORD = "1"
MAX_CUHKSZ_TITLE_TERMS = 4
GENERIC_CUHKSZ_QUERY_TOKENS = {
    "engineer",
    "intern",
    "internship",
    "python",
    "matlab",
    "pytorch",
    "tensorflow",
    "fastapi",
    "ai",
    "health",
    "algorithm",
    "algorithms",
    "signal",
    "signals",
    "processing",
    "physiological",
    "biomedical",
    "sql",
    "backend",
    "application",
    "software",
    "developer",
}

COMPANY_LABELS = ["公司名称", "企业名称"]
LOCATION_LABELS = ["工作地点", "地点"]
EMPLOYMENT_TYPE_LABELS = ["工作性质", "职位性质"]
CATEGORY_LABELS = ["职位类别", "岗位类别"]
HEADCOUNT_LABELS = ["招聘人数", "人数"]
SALARY_LABELS = ["薪资", "薪资待遇"]
PUBLISHED_DATE_LABELS = ["发布时间"]
END_DATE_LABELS = ["结束时间", "截止时间"]
JOB_DESCRIPTION_LABELS = ["工作内容描述", "岗位职责", "职位描述", "任职要求"]
COMPANY_INTRO_LABELS = ["企业简介", "公司简介"]
CONTACT_INFO_LABELS = ["联系方式", "申请方式", "投递方式"]


def build_cuhksz_search_url(title: str, *, city: str | None = None) -> str:
    params = {
        "title": title.strip(),
        "title_type": CUHKSZ_TITLE_TYPE_KEYWORD,
        "city": (city or "").strip(),
        "d_industry": "",
        "nature": "",
        "d_skill": "",
        "d_category": "",
    }
    return f"{CUHKSZ_CAREER_SEARCH_URL}?{urlencode(params)}"


def build_cuhksz_title_terms(query: str, *, limit: int = MAX_CUHKSZ_TITLE_TERMS) -> list[str]:
    raw_query = _clean_text(query)
    if not raw_query:
        return []

    terms: list[str] = []
    terms.extend(_expand_english_health_query(raw_query))

    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", raw_query)
    for chunk in cjk_chunks:
        terms.extend(_expand_cjk_query_chunk(chunk))

    latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", raw_query)
    for token in latin_tokens:
        normalized = token.strip()
        if normalized.lower() in GENERIC_CUHKSZ_QUERY_TOKENS:
            continue
        if len(normalized) <= 8 or normalized.isupper():
            terms.append(normalized)

    return _dedupe(terms)[:limit]


def _expand_english_health_query(query: str) -> list[str]:
    lowered = query.lower()
    terms: list[str] = []
    if "algorithm" in lowered or "algorithms" in lowered:
        terms.append("算法")
    if "physiological signal" in lowered or "biosignal" in lowered:
        terms.append("生理信号")
    if ("health" in lowered or "biomedical" in lowered) and (
        "algorithm" in lowered or "ai" in lowered
    ):
        terms.append("健康算法")
    return terms


def parse_cuhksz_job_list(html: str, base_url: str) -> list[SimpleNamespace]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[SimpleNamespace] = []
    for row in soup.select("li"):
        title_node = row.select_one("a.f18") or row.find("a", href=re.compile(r"/job/view/id/"))
        if title_node is None:
            continue
        href = str(title_node.get("href") or "").strip()
        if not href:
            continue
        company_node = row.select_one(".sousuo_list_com a")
        meta_node = row.select_one(".mt10.mb10")
        meta_text = _clean_text(meta_node.get_text(" ", strip=True)) if meta_node else ""
        meta_parts = [part.strip() for part in re.split(r"[|锝-]+", meta_text) if part.strip()]
        time_node = row.select_one(".sousuo_list_time")
        time_text = _clean_text(time_node.get_text(" ", strip=True)) if time_node else ""
        dates = re.findall(r"\d{3,4}-\d{2}-\d{2}", time_text)
        items.append(
            SimpleNamespace(
                title=_clean_text(title_node.get_text(" ", strip=True)),
                company=_clean_text(company_node.get_text(" ", strip=True)) if company_node else None,
                location=meta_parts[0] if meta_parts else None,
                job_type=meta_parts[1] if len(meta_parts) > 1 else None,
                education=meta_parts[2] if len(meta_parts) > 2 else None,
                published_at=dates[0] if dates else None,
                deadline=dates[1] if len(dates) > 1 else None,
                detail_url=urljoin(base_url, href),
                source="cuhksz_career",
            )
        )
    return items


def extract_cuhksz_jd_text(detail_html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup.select("script,style,noscript,header,footer,nav"):
        node.decompose()
    main = soup.select_one("main") or soup.body or soup
    text = _clean_text(main.get_text(" ", strip=True))
    warnings: list[str] = []
    if len(text) < 120:
        warnings.append("jd_text_too_short")
    return text, warnings


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
        title_terms = build_cuhksz_title_terms(query) or [_clean_text(query)]
        search_urls = (
            [self.search_url]
            if self.list_page_html is not None
            else [build_cuhksz_search_url(term) for term in title_terms if term]
        )
        query_terms = _tokenize(query)
        location_terms = _tokenize(location)

        candidates: list[RawJobCandidate] = []
        seen_urls: set[str] = set()
        for search_url in search_urls:
            list_html = self.list_page_html if self.list_page_html is not None else self._fetch(search_url)
            list_items = parse_cuhksz_job_list(list_html, search_url)
            for item in list_items:
                candidate = _build_list_candidate(item, provider_name=self.provider_name)
                if candidate is None or not candidate.source_url or candidate.source_url.lower() in seen_urls:
                    continue
                seen_urls.add(candidate.source_url.lower())

                if self.list_page_html is not None and (query_terms or location_terms):
                    if not _matches(candidate, query_terms=query_terms, location_terms=location_terms):
                        candidate = candidate.model_copy(
                            update={
                                "provider_warnings": candidate.provider_warnings + [NO_PROVIDER_MATCH_WARNING],
                            }
                        )

                detailed = self.fetch_job_detail(candidate)
                if _is_low_quality_candidate(detailed):
                    continue
                candidates.append(detailed)
                if len(candidates) >= limit:
                    break
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


def _build_list_candidate(item: object, *, provider_name: str) -> RawJobCandidate | None:
    title = _clean_text(getattr(item, "title", ""))
    detail_url = _clean_text(getattr(item, "detail_url", ""))
    if not title or not detail_url or not _is_allowed_detail_url(detail_url):
        return None

    company = _clean_text(getattr(item, "company", ""))
    location = _clean_text(getattr(item, "location", ""))
    snippet_lines = [
        part
        for part in [
            company,
            location,
            _clean_text(getattr(item, "job_type", "")),
            _clean_text(getattr(item, "education", "")),
            _format_dates(getattr(item, "published_at", None), getattr(item, "deadline", None)),
        ]
        if part
    ]
    return RawJobCandidate(
        title=title,
        company=company or None,
        location=location or None,
        source_url=detail_url,
        source_provider=provider_name,
        snippet=" | ".join(snippet_lines) or title,
        raw_description=None,
    )


def _expand_cjk_query_chunk(chunk: str) -> list[str]:
    terms: list[str] = []
    if "算法" in chunk:
        terms.append("算法")
    if "生理信号" in chunk:
        terms.append("生理信号")
    if "健康" in chunk and "算法" in chunk:
        terms.append("健康算法")

    suffixes = ["实习生", "工程师", "岗位", "职位"]
    stripped = chunk
    for suffix in suffixes:
        if chunk.endswith(suffix) and len(chunk) > len(suffix) + 1:
            stripped = chunk[: -len(suffix)]
            break

    if not terms:
        terms.append(stripped)
        if stripped != chunk:
            terms.append(chunk)
    return terms


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _is_low_quality_candidate(candidate: RawJobCandidate) -> bool:
    title = _clean_text(candidate.title or "")
    company = _clean_text(candidate.company or "")
    if title in {"招聘信息", "职位详情", "岗位详情"}:
        return True
    if company in {"：", ":", "-", "不限"}:
        return True
    if not title or not candidate.source_url:
        return True
    return False


def _is_allowed_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc in CUHKSZ_CAREER_ALLOWED_DOMAINS


def _parse_detail_fields(detail_html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup.select("script,style,noscript"):
        node.decompose()

    title = _first_text(soup, ["h1", ".job_name", ".position_name"])
    company = _search_label(detail_html, COMPANY_LABELS)
    location = _search_label(detail_html, LOCATION_LABELS)
    employment_type = _search_label(detail_html, EMPLOYMENT_TYPE_LABELS)
    category = _search_label(detail_html, CATEGORY_LABELS)
    headcount = _search_label(detail_html, HEADCOUNT_LABELS)
    salary = _search_label(detail_html, SALARY_LABELS)
    published_date = _search_label(detail_html, PUBLISHED_DATE_LABELS)
    end_date = _search_label(detail_html, END_DATE_LABELS)
    extracted_jd_text, _warnings = extract_cuhksz_jd_text(detail_html)
    job_description = _extract_section(detail_html, JOB_DESCRIPTION_LABELS) or extracted_jd_text
    company_intro = _extract_section(detail_html, COMPANY_INTRO_LABELS)
    contact_info = _extract_section(detail_html, CONTACT_INFO_LABELS)

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
                text = _extract_text_fragment(child)
                if text:
                    section_parts.append(text)
        else:
            for sibling in heading.next_siblings:
                sibling_name = getattr(sibling, "name", None)
                if sibling_name in {"h1", "h2", "h3"}:
                    break
                text = _extract_text_fragment(sibling)
                if text:
                    section_parts.append(text)

        section_text = " ".join(section_parts).strip()
        if section_text:
            return section_text
    return None


def _extract_text_fragment(node: object) -> str:
    if hasattr(node, "get_text"):
        return _clean_text(node.get_text(" ", strip=True))
    return _clean_text(str(node))


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
