from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_providers.base import JobSearchProviderError
from app.services.job_search_providers.multi_source_provider import MultiSourceJobSearchProvider
from experiments.provider_recall_calibration import (
    matched_signals,
    render_markdown,
    resolve_provider_selection,
    run_case,
    run_provider_query,
    sanitize_source_attempt,
    summarize_query_recall,
)
from tests.fixtures.resumes.multidomain_flow_cases import MULTIDOMAIN_FLOW_CASES


class FakeMultiSourceProvider:
    provider_name = "multi_source:cuhksz_career,remoteok"
    provider_kind = "hybrid"
    source_names = ["cuhksz_career", "remoteok"]

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        return [
            RawJobCandidate(
                title="Brand Marketing Intern",
                company="Example Careers",
                location=location,
                source_url="https://career.example.com/jobs/brand-marketing-intern",
                source_provider="cuhksz_career",
                snippet=f"Campaign planning and market research for {query}",
                raw_description=f"Detailed campaign planning and market research for {query}",
                discovery_query=query,
                discovery_rank=1,
                detail_status="detail_fetched",
            ),
            RawJobCandidate(
                title="Brand Marketing Intern duplicate",
                company="Example Careers",
                location=location,
                source_url="https://career.example.com/jobs/brand-marketing-intern",
                source_provider="cuhksz_career",
                snippet="Duplicate public listing.",
                raw_description="Duplicate public listing.",
                discovery_query=query,
                discovery_rank=2,
                detail_status="detail_fetched",
            ),
            RawJobCandidate(
                title=f"{query} Remote Assistant",
                company="Remote Example",
                location="Remote",
                source_url=f"https://remoteok.com/{query.lower().replace(' ', '-')}",
                source_provider="remoteok",
                snippet="Consumer insight, social media content, and event coordination.",
                raw_description="Consumer insight, social media content, and event coordination.",
                discovery_query=query,
                discovery_rank=3,
                detail_status="official_json_api",
            ),
        ][:limit]


def test_resolve_provider_selection_defaults_multi_source_to_frontend_sources() -> None:
    provider_name, selected_sources = resolve_provider_selection("multi_source", [])

    assert provider_name == "multi_source:cuhksz_career,linkedin,remoteok"
    assert selected_sources == ["cuhksz_career", "linkedin", "remoteok"]


def test_matched_signals_uses_case_insensitive_substrings() -> None:
    signals = matched_signals(
        "This role covers Campaign Planning and Market Research.",
        ["campaign planning", "market research", "Excel"],
    )

    assert signals == ["campaign planning", "market research"]


def test_provider_recall_case_is_json_serializable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "provider-recall.sqlite3"))
    client = TestClient(app)
    try:
        result = run_case(
            client=client,
            case=MULTIDOMAIN_FLOW_CASES[0],
            provider=FakeMultiSourceProvider(),
            provider_name="multi_source:cuhksz_career,remoteok",
            selected_sources=["cuhksz_career", "remoteok"],
            queries_per_case=2,
            limit_per_query=3,
            max_results=10,
            include_location=True,
        )
    finally:
        client.close()

    assert result["raw_candidate_count"] == 6
    assert result["deduped_candidate_count"] >= 3
    assert result["duplicate_count"] >= 1
    assert result["source_stats"]
    assert result["logical_source_attempt_count"] == 2
    assert result["external_http_request_count"] is None
    assert result["query_results"][0]["new_candidate_count"] == 2
    assert result["query_results"][1]["new_candidate_count"] == 1
    assert result["query_results"][1]["duplicate_candidate_count"] == 2
    assert {item["source_provider"] for item in result["source_stats"]} == {
        "cuhksz_career",
        "remoteok",
    }
    assert result["top_candidates"]
    json.dumps(result, ensure_ascii=False)


def test_query_recall_credits_each_exact_candidate_to_first_seen_query() -> None:
    candidate = RawJobCandidate(
        title="AI Intern",
        company="Example",
        location="Remote",
        snippet="AI internship.",
        source_url="https://example.com/jobs/1",
        source_provider="linkedin",
        raw_description="Complete job description.",
    )

    summaries = summarize_query_recall(
        [{"candidates": [candidate]}, {"candidates": [candidate]}]
    )

    assert summaries[0]["new_candidate_count"] == 1
    assert summaries[1]["new_candidate_count"] == 0
    assert summaries[1]["duplicate_candidate_count"] == 1


def test_multi_source_partial_failure_is_counted_and_error_is_sanitized() -> None:
    class SuccessfulProvider:
        provider_name = "remoteok"

        def search_jobs(self, *, query: str, location: str | None, limit: int):
            return [
                RawJobCandidate(
                    title="Remote Intern",
                    company="Example",
                    location="Remote",
                    source_url="https://remote.example/jobs/1",
                    source_provider="remoteok",
                    snippet=query,
                )
            ]

    class FailingProvider:
        provider_name = "linkedin"

        def search_jobs(self, *, query: str, location: str | None, limit: int):
            raise JobSearchProviderError("private provider detail must not be persisted")

    provider = MultiSourceJobSearchProvider([SuccessfulProvider(), FailingProvider()])

    result = run_provider_query(provider, query="AI Intern", location=None, limit=5)
    attempts = [sanitize_source_attempt(item) for item in provider.source_attempts]

    assert result["returned_count"] == 1
    assert result["error_code"] is None
    assert [item["error_code"] for item in attempts] == [None, "JobSearchProviderError"]
    assert "private provider detail" not in json.dumps(attempts)


def test_provider_recall_markdown_contains_source_breakdown() -> None:
    markdown = render_markdown(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "provider": "multi_source:cuhksz_career,remoteok",
            "selected_sources": ["cuhksz_career", "remoteok"],
            "provider_statuses": [
                {
                    "provider": "multi_source",
                    "configured": True,
                    "source_kind": "hybrid",
                    "detail_strategy": "mixed_source_strategy",
                    "reason": None,
                }
            ],
            "queries_per_case": 1,
            "limit_per_query": 10,
            "max_results": 10,
            "include_location": True,
            "results": [
                {
                    "case_id": "brand_marketing",
                    "source_file": "resume.txt",
                    "target_roles": ["Brand Marketing Intern"],
                    "target_directions": ["Brand marketing"],
                    "preferred_locations": ["Shanghai"],
                    "raw_candidate_count": 2,
                    "deduped_candidate_count": 1,
                    "duplicate_count": 1,
                    "truncated_candidate_count": 0,
                    "missing_source_url_count": 0,
                    "missing_detail_count": 0,
                    "source_provider_counts": {"cuhksz_career": 1},
                    "source_stats": [
                        {
                            "source_provider": "cuhksz_career",
                            "raw_candidate_count": 2,
                            "deduped_candidate_count": 1,
                            "unretained_candidate_count": 1,
                            "missing_url_count": 0,
                            "missing_detail_count": 0,
                            "warning_count": 0,
                            "detail_coverage_rate": 1.0,
                        }
                    ],
                    "provider_queries": ["Brand Marketing Intern"],
                    "ranking_signals": ["campaign planning"],
                    "provider_search_urls": [],
                    "query_results": [
                        {
                            "query": "Brand Marketing Intern",
                            "location": "Shanghai",
                            "returned_count": 2,
                            "error": None,
                        }
                    ],
                    "top_candidates": [
                        {
                            "source_provider": "cuhksz_career",
                            "title": "Brand Marketing Intern",
                            "domain": "career.example.com",
                            "detail_status": "detail_fetched",
                            "matched_signals": ["campaign planning"],
                            "source_url": "https://career.example.com/jobs/1",
                        }
                    ],
                }
            ],
        }
    )

    assert "Provider Recall Calibration" in markdown
    assert "### Source Stats" in markdown
    assert "cuhksz_career" in markdown
    assert "raw candidates: 2" in markdown
