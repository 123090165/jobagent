from __future__ import annotations

from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_recall_metrics import (
    build_source_recall_stats,
    candidate_recall_key,
    dedupe_cross_source_reposts,
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


def test_candidate_recall_key_canonicalizes_boss_detail_query_params() -> None:
    first = _candidate(
        title="Algorithm Intern",
        source_provider="boss_zhipin",
        source_url="https://www.zhipin.com/job_detail/ABC123.html?lid=one&securityId=first",
        detail_status="browser_helper_payload",
    )
    second = _candidate(
        title="Algorithm Intern",
        source_provider="boss_zhipin",
        source_url="https://www.zhipin.com/job_detail/ABC123.html?lid=two&securityId=second",
        detail_status="browser_helper_payload",
    )

    deduped, duplicate_count, truncated_count = dedupe_recall_candidates([first, second], limit=10)

    assert candidate_recall_key(first) == candidate_recall_key(second)
    assert len(deduped) == 1
    assert duplicate_count == 1
    assert truncated_count == 0


def test_candidate_recall_key_canonicalizes_cuhksz_detail_query_params() -> None:
    first = _candidate(
        title="AI Algorithm Intern",
        source_provider="cuhksz_career",
        source_url="https://career.cuhk.edu.cn/job/view/id/468293?from=search",
        detail_status="native_detail_page",
    )
    second = _candidate(
        title="AI Algorithm Intern",
        source_provider="cuhksz_career",
        source_url="https://career.cuhk.edu.cn/job/view/id/468293?keyword=AI",
        detail_status="native_detail_page",
    )

    deduped, duplicate_count, truncated_count = dedupe_recall_candidates([first, second], limit=10)

    assert candidate_recall_key(first) == candidate_recall_key(second)
    assert len(deduped) == 1
    assert duplicate_count == 1
    assert truncated_count == 0


def test_candidate_recall_key_canonicalizes_linkedin_job_urls() -> None:
    first = _candidate(
        title="Machine Learning Intern",
        source_provider="linkedin",
        source_url="https://www.linkedin.com/jobs/view/1234567890/?trk=public_jobs_topcard-title",
        detail_status="linkedin_external_link",
    )
    second = _candidate(
        title="Machine Learning Intern",
        source_provider="linkedin",
        source_url="https://www.linkedin.com/jobs/search/?currentJobId=1234567890&keywords=machine%20learning",
        detail_status="linkedin_external_link",
    )

    deduped, duplicate_count, truncated_count = dedupe_recall_candidates([first, second], limit=10)

    assert candidate_recall_key(first) == candidate_recall_key(second)
    assert len(deduped) == 1
    assert duplicate_count == 1
    assert truncated_count == 0


def test_cross_source_repost_keeps_the_candidate_with_better_jd_evidence() -> None:
    linkedin = _candidate(
        title="Logistics Data Analyst",
        source_provider="linkedin",
        source_url="https://linkedin.com/jobs/view/123",
        detail_status="linkedin_external_link",
    )
    remoteok = _candidate(
        title="Logistics Data Analyst",
        source_provider="remoteok",
        source_url="https://remoteok.com/jobs/456",
        detail_status="official_json_api",
        raw_description="Full job description with responsibilities and requirements.",
    )

    retained, duplicate_count = dedupe_cross_source_reposts([linkedin, remoteok])

    assert retained == [remoteok]
    assert duplicate_count == 1


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


def test_incomplete_fetched_detail_is_not_counted_as_detail_coverage() -> None:
    candidate = _candidate(
        title="Sparse CUHKSZ Job",
        source_provider="cuhksz_career",
        source_url="https://career.cuhk.edu.cn/job/view/id/1",
        detail_status="detail_fetched_incomplete",
        raw_description="Only a short responsibilities fragment.",
    )

    stats = build_source_recall_stats([candidate], [candidate])[0]

    assert has_missing_detail(candidate) is True
    assert stats.missing_detail_count == 1
    assert stats.detail_coverage_rate == 0.0
