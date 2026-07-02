from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass

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
    if candidate.source_url:
        return candidate.source_url.strip().lower().rstrip("/")
    return ":".join(
        [
            (candidate.title or "").strip().lower(),
            (candidate.company or "").strip().lower(),
            (candidate.location or "").strip().lower(),
        ]
    )


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


def _source_name(candidate: RawJobCandidate) -> str:
    return (candidate.source_provider or "unknown").strip() or "unknown"
