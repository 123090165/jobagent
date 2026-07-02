from __future__ import annotations

from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_recall_metrics import (
    build_source_recall_stats,
    dedupe_recall_candidates,
    has_missing_detail,
)


def _candidate(
    *,
    title: str,
    source_provider: str,
    source_url: str | None,
    detail_status: str | None,
    raw_description: str | None = None,
) -> RawJobCandidate:
    return RawJobCandidate(
        title=title,
        company="Example",
        location="Remote",
        source_url=source_url,
        source_provider=source_provider,
        snippet=f"{title} snippet",
        raw_description=raw_description,
        detail_status=detail_status,
    )


def test_dedupe_recall_candidates_prefers_source_url_and_counts_duplicates() -> None:
    candidates = [
        _candidate(
            title="Brand Marketing Intern",
            source_provider="linkedin",
            source_url="https://linkedin.com/jobs/view/1",
            detail_status="linkedin_external_link",
        ),
        _candidate(
            title="Duplicate",
            source_provider="linkedin",
            source_url="https://linkedin.com/jobs/view/1",
            detail_status="linkedin_external_link",
        ),
        _candidate(
            title="Remote Marketing Intern",
            source_provider="remoteok",
            source_url="https://remoteok.com/jobs/2",
            detail_status="official_json_api",
            raw_description="Detailed official JSON description.",
        ),
    ]

    deduped, duplicate_count, truncated_count = dedupe_recall_candidates(candidates, limit=10)

    assert len(deduped) == 2
    assert duplicate_count == 1
    assert truncated_count == 0


def test_source_recall_stats_report_missing_detail_and_warnings() -> None:
    raw = [
        _candidate(
            title="LinkedIn Job",
            source_provider="linkedin",
            source_url="https://linkedin.com/jobs/view/1",
            detail_status="linkedin_external_link",
        ),
        _candidate(
            title="LinkedIn Job duplicate",
            source_provider="linkedin",
            source_url="https://linkedin.com/jobs/view/1",
            detail_status="linkedin_external_link",
        ),
        _candidate(
            title="RemoteOK Job",
            source_provider="remoteok",
            source_url="https://remoteok.com/jobs/2",
            detail_status="official_json_api",
            raw_description="Detailed official JSON description.",
        ),
    ]
    deduped, _duplicates, _truncated = dedupe_recall_candidates(raw, limit=10)
    deduped[0].provider_warnings.append("External link only.")

    stats = {item.source_provider: item for item in build_source_recall_stats(raw, deduped)}

    assert stats["linkedin"].raw_candidate_count == 2
    assert stats["linkedin"].deduped_candidate_count == 1
    assert stats["linkedin"].unretained_candidate_count == 1
    assert stats["linkedin"].missing_detail_count == 1
    assert stats["linkedin"].detail_coverage_rate == 0.0
    assert stats["linkedin"].warning_count == 1
    assert stats["remoteok"].detail_coverage_rate == 1.0
    assert has_missing_detail(deduped[0]) is True
    assert has_missing_detail(deduped[1]) is False
