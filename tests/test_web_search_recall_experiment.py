from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.job_search_providers.base import RawJobCandidate
from experiments.web_search_recall_check import (
    dedupe_candidates,
    matched_signals,
    render_markdown,
    run_case,
)
from tests.fixtures.resumes.multidomain_flow_cases import MULTIDOMAIN_FLOW_CASES


class FakeSearchProvider:
    provider_name = "serper_web"
    provider_kind = "search_engine"

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        return [
            RawJobCandidate(
                title="Brand Marketing Intern",
                company="Example Careers",
                location=location,
                source_url="https://career.example.com/jobs/brand-marketing-intern",
                source_provider=self.provider_name,
                snippet=f"Campaign planning and market research for {query}",
                raw_description=f"Campaign planning and market research for {query}",
                discovery_query=query,
                discovery_rank=1,
                detail_status="search_result_snippet_only",
            ),
            RawJobCandidate(
                title=f"{query} Assistant",
                company="Example Search",
                location=location,
                source_url=f"https://jobs.example.org/{query.lower().replace(' ', '-')}",
                source_provider=self.provider_name,
                snippet="Consumer insight, social media content, and event coordination.",
                raw_description="Consumer insight, social media content, and event coordination.",
                discovery_query=query,
                discovery_rank=2,
                detail_status="search_result_snippet_only",
            ),
        ][:limit]


def test_dedupe_candidates_prefers_source_url() -> None:
    candidates = [
        RawJobCandidate(
            title="A",
            company="C",
            location=None,
            source_url="https://example.com/jobs/a",
            source_provider="serper_web",
            snippet="one",
        ),
        RawJobCandidate(
            title="A duplicate",
            company="C",
            location=None,
            source_url="https://example.com/jobs/a",
            source_provider="serper_web",
            snippet="two",
        ),
    ]

    assert len(dedupe_candidates(candidates)) == 1


def test_matched_signals_uses_case_insensitive_substrings() -> None:
    signals = matched_signals(
        "This role covers Campaign Planning and Market Research.",
        ["campaign planning", "market research", "Excel"],
    )

    assert signals == ["campaign planning", "market research"]


def test_web_search_recall_case_is_json_serializable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "web-recall.sqlite3"))
    client = TestClient(app)
    try:
        result = run_case(
            client=client,
            case=MULTIDOMAIN_FLOW_CASES[0],
            provider=FakeSearchProvider(),
            queries_per_case=2,
            limit_per_query=2,
            include_location=True,
        )
    finally:
        client.close()

    assert result["raw_candidate_count"] == 4
    assert result["deduped_candidate_count"] == 3
    assert result["duplicate_count"] == 1
    assert result["top_candidates"]
    json.dumps(result, ensure_ascii=False)


def test_web_search_recall_markdown_contains_funnel_counts() -> None:
    markdown = render_markdown(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "provider": "serper_web",
            "search_sites": ["career.example.com"],
            "queries_per_case": 1,
            "limit_per_query": 10,
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
                    "source_domains": {"career.example.com": 1},
                    "recall_queries": ["Brand Marketing Intern"],
                    "ranking_signals": ["campaign planning"],
                    "query_results": [
                        {
                            "query": "Brand Marketing Intern",
                            "location": "Shanghai",
                            "returned_count": 2,
                        }
                    ],
                    "top_candidates": [
                        {
                            "title": "Brand Marketing Intern",
                            "domain": "career.example.com",
                            "matched_signals": ["campaign planning"],
                            "source_url": "https://career.example.com/jobs/1",
                        }
                    ],
                }
            ],
        }
    )

    assert "raw candidates: 2" in markdown
    assert "deduped candidates: 1" in markdown
    assert "Brand Marketing Intern" in markdown
