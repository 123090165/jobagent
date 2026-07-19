from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, urlparse

from app.services.job_search_providers.base import RawJobCandidate

SNIPPET_ONLY_DETAIL_STATUSES = {
    None,
    "",
    "detail_failed",
    "detail_missing_url",
    "detail_pending",
    "linkedin_external_link",
    "search_result_snippet_only",
}


@dataclass(frozen=True)
class ProviderSourceRecallStat:
    source_provider: str
    raw_candidate_count: int
    deduped_candidate_count: int
    unretained_candidate_count: int
    missing_url_count: int
    missing_detail_count: int
    warning_count: int
    detail_coverage_rate: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def candidate_recall_key(candidate: RawJobCandidate) -> str:
    canonical_url = canonical_source_url_key(candidate.source_url)
    if canonical_url:
        return canonical_url
    return ":".join(
        [
            (candidate.title or "").strip().lower(),
            (candidate.company or "").strip().lower(),
            (candidate.location or "").strip().lower(),
        ]
    )


def canonical_source_url_key(source_url: str | None) -> str | None:
    """Return the stable provider-agnostic URL identity used for recall/result dedupe."""
    if not source_url:
        return None
    raw_url = source_url.strip()
    if not raw_url:
        return None
    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return raw_url.lower().rstrip("/")

    if not parsed.netloc and re.match(r"^[a-z0-9.-]+\.[a-z]{2,}/", raw_url, re.IGNORECASE):
        parsed = urlparse(f"https://{raw_url}")

    netloc = _canonical_host(parsed.netloc)
    path = re.sub(r"/+", "/", parsed.path or "").rstrip("/")
    if not path:
        path = "/"

    zhipin_match = re.search(r"/job_detail/([^/?#]+)", path, re.IGNORECASE)
    if ("zhipin.com" in netloc or not netloc) and zhipin_match:
        host = netloc or "zhipin.com"
        return f"{host}/job_detail/{zhipin_match.group(1).lower()}"

    cuhksz_match = re.search(r"/job/view/id/([^/?#]+)", path, re.IGNORECASE)
    if ("career.cuhk.edu.cn" in netloc or not netloc) and cuhksz_match:
        host = netloc or "career.cuhk.edu.cn"
        return f"{host}/job/view/id/{cuhksz_match.group(1).lower()}"

    linkedin_match = re.search(r"/jobs/view/([^/?#]+)", path, re.IGNORECASE)
    if ("linkedin.com" in netloc or not netloc) and linkedin_match:
        return f"linkedin.com/jobs/view/{linkedin_match.group(1).lower()}"

    if "linkedin.com" in netloc:
        current_job_id = (parse_qs(parsed.query).get("currentJobId") or [""])[0].strip()
        if current_job_id:
            return f"linkedin.com/jobs/view/{current_job_id.lower()}"

    if netloc:
        return f"{netloc}{path.lower()}"
    return path.lower()


def _canonical_host(netloc: str) -> str:
    host = netloc.lower().removeprefix("www.")
    if host.endswith(".zhipin.com"):
        return "zhipin.com"
    if host.endswith(".linkedin.com"):
        return "linkedin.com"
    return host


def dedupe_recall_candidates(
    candidates: Iterable[RawJobCandidate],
    *,
    limit: int | None = None,
) -> tuple[list[RawJobCandidate], int, int]:
    deduped: list[RawJobCandidate] = []
    seen: set[str] = set()
    duplicate_count = 0
    truncated_count = 0
    for candidate in candidates:
        key = candidate_recall_key(candidate)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        if limit is not None and len(deduped) >= limit:
            truncated_count += 1
            continue
        deduped.append(candidate)
    return deduped, duplicate_count, truncated_count


def dedupe_cross_source_reposts(
    candidates: Iterable[RawJobCandidate],
) -> tuple[list[RawJobCandidate], int]:
    """Collapse conservative title/company/location matches across different sources."""
    retained: list[RawJobCandidate] = []
    cluster_indexes: dict[str, int] = {}
    duplicate_count = 0
    for candidate in candidates:
        identity = _cross_source_identity(candidate)
        existing_index = cluster_indexes.get(identity) if identity else None
        if existing_index is None:
            if identity:
                cluster_indexes[identity] = len(retained)
            retained.append(candidate)
            continue

        existing = retained[existing_index]
        if existing.source_provider == candidate.source_provider:
            retained.append(candidate)
            continue
        duplicate_count += 1
        if _candidate_evidence_quality(candidate) > _candidate_evidence_quality(existing):
            retained[existing_index] = candidate
    return retained, duplicate_count


def build_source_recall_stats(
    raw_candidates: Iterable[RawJobCandidate],
    deduped_candidates: Iterable[RawJobCandidate],
) -> list[ProviderSourceRecallStat]:
    raw_items = list(raw_candidates)
    deduped_items = list(deduped_candidates)
    raw_counts = Counter(_source_name(candidate) for candidate in raw_items)
    deduped_counts = Counter(_source_name(candidate) for candidate in deduped_items)
    missing_url_counts = Counter(
        _source_name(candidate) for candidate in deduped_items if not candidate.source_url
    )
    missing_detail_counts = Counter(
        _source_name(candidate) for candidate in deduped_items if has_missing_detail(candidate)
    )
    warning_counts = Counter()
    for candidate in deduped_items:
        warning_counts[_source_name(candidate)] += len(candidate.provider_warnings)

    source_names = sorted(set(raw_counts) | set(deduped_counts))
    stats: list[ProviderSourceRecallStat] = []
    for source in source_names:
        deduped_count = deduped_counts[source]
        missing_detail_count = missing_detail_counts[source]
        detail_coverage_rate = (
            round((deduped_count - missing_detail_count) / deduped_count, 3)
            if deduped_count
            else 0.0
        )
        stats.append(
            ProviderSourceRecallStat(
                source_provider=source,
                raw_candidate_count=raw_counts[source],
                deduped_candidate_count=deduped_count,
                unretained_candidate_count=max(0, raw_counts[source] - deduped_count),
                missing_url_count=missing_url_counts[source],
                missing_detail_count=missing_detail_count,
                warning_count=warning_counts[source],
                detail_coverage_rate=detail_coverage_rate,
            )
        )
    return stats


def has_missing_detail(candidate: RawJobCandidate) -> bool:
    status = (candidate.detail_status or "").strip()
    if status in SNIPPET_ONLY_DETAIL_STATUSES:
        return True
    return not bool((candidate.raw_description or "").strip())


def _cross_source_identity(candidate: RawJobCandidate) -> str | None:
    parts = [
        _identity_text(candidate.title),
        _identity_text(candidate.company),
        _identity_text(candidate.location),
    ]
    if not all(parts):
        return None
    return "|".join(parts)


def _identity_text(value: str | None) -> str:
    return "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", (value or "").casefold()))


def _candidate_evidence_quality(candidate: RawJobCandidate) -> tuple[int, int, int, int]:
    description = (candidate.raw_description or "").strip()
    return (
        int(not has_missing_detail(candidate)),
        len(description),
        int(bool(candidate.source_url)),
        -len(candidate.provider_warnings),
    )


def _source_name(candidate: RawJobCandidate) -> str:
    return (candidate.source_provider or "unknown").strip() or "unknown"
