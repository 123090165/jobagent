from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable

from app.services.job_search_providers.base import JobSearchProviderError, RawJobCandidate

REMOTEOK_API_URL = "https://remoteok.com/api"
REMOTEOK_USER_AGENT = "JobAgent/0.1 remoteok-provider"


class RemoteOKProvider:
    provider_name = "remoteok"
    provider_kind = "native_api"
    detail_strategy = "official_json_api"
    search_url = REMOTEOK_API_URL

    def __init__(
        self,
        *,
        fetcher: Callable[[urllib.request.Request], bytes] | None = None,
    ) -> None:
        self.fetcher = fetcher or _fetch_request_bytes
        self._cache: list[dict[str, object]] | None = None

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        records = self._load_records()
        query_terms = _tokenize(query)
        location_terms = _tokenize(location)
        candidates: list[RawJobCandidate] = []
        for index, record in enumerate(records):
            candidate = _candidate_from_record(record, query=query, index=index + 1)
            if candidate is None:
                continue
            haystack = _candidate_haystack(candidate, record)
            if query_terms and not any(term in haystack for term in query_terms):
                continue
            if location_terms and not any(term in haystack for term in location_terms):
                candidate = candidate.model_copy(
                    update={
                        "provider_warnings": candidate.provider_warnings
                        + ["RemoteOK location did not explicitly match the preferred location."],
                    }
                )
            candidates.append(candidate)
            if len(candidates) >= limit:
                break
        return candidates

    def _load_records(self) -> list[dict[str, object]]:
        if self._cache is not None:
            return self._cache
        request = urllib.request.Request(
            REMOTEOK_API_URL,
            headers={"User-Agent": REMOTEOK_USER_AGENT},
            method="GET",
        )
        try:
            body = self.fetcher(request)
        except urllib.error.HTTPError as exc:
            raise JobSearchProviderError(f"RemoteOK request failed with HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise JobSearchProviderError(f"RemoteOK request failed: {exc.reason}.") from exc
        except TimeoutError as exc:
            raise JobSearchProviderError("RemoteOK request timed out.") from exc
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise JobSearchProviderError("RemoteOK returned invalid JSON.") from exc
        if not isinstance(data, list):
            raise JobSearchProviderError("RemoteOK returned an unexpected payload.")
        self._cache = [item for item in data if isinstance(item, dict) and item.get("id")]
        return self._cache


def _fetch_request_bytes(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=20.0) as response:
        return response.read()


def _candidate_from_record(
    record: dict[str, object],
    *,
    query: str,
    index: int,
) -> RawJobCandidate | None:
    title = _clean_text(str(record.get("position") or ""))
    company = _clean_text(str(record.get("company") or ""))
    source_url = _clean_text(str(record.get("url") or record.get("apply_url") or ""))
    if not title or not source_url:
        return None
    description = _clean_html(str(record.get("description") or ""))
    tags = [str(tag).strip() for tag in record.get("tags") or [] if str(tag).strip()]
    location = _clean_text(str(record.get("location") or "")) or "Remote"
    snippet_parts = [description[:260]]
    if tags:
        snippet_parts.append("Tags: " + ", ".join(tags[:8]))
    salary = _salary_text(record)
    if salary:
        snippet_parts.append(salary)
    return RawJobCandidate(
        title=title,
        company=company or "RemoteOK",
        location=location,
        source_url=source_url,
        source_provider="remoteok",
        snippet=" | ".join(part for part in snippet_parts if part),
        raw_description=description,
        discovery_query=query,
        discovery_rank=index,
        detail_status="official_json_api",
        provider_warnings=["RemoteOK API source; link back to RemoteOK when displaying this job."],
    )


def _candidate_haystack(candidate: RawJobCandidate, record: dict[str, object]) -> str:
    tags = " ".join(str(tag) for tag in record.get("tags") or [])
    return " ".join(
        [
            candidate.title or "",
            candidate.company or "",
            candidate.location or "",
            candidate.snippet or "",
            tags,
        ]
    ).lower()


def _salary_text(record: dict[str, object]) -> str:
    salary_min = int(record.get("salary_min") or 0)
    salary_max = int(record.get("salary_max") or 0)
    if not salary_min and not salary_max:
        return ""
    if salary_min and salary_max:
        return f"Salary: {salary_min}-{salary_max}"
    return f"Salary: {salary_min or salary_max}"


def _clean_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return _clean_text(html.unescape(without_tags))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [
        token
        for token in re.split(r"[^a-z0-9\u4e00-\u9fff+#.-]+", text.lower())
        if len(token) >= 2
    ]
