from __future__ import annotations

import json

from app.services.job_search_providers.base import RawJobCandidate
from experiments.provider_live_smoke import (
    render_markdown,
    resolve_smoke_query,
    run_smoke_check,
)


class FakeProvider:
    provider_name = "fake"
    provider_kind = "native_job_board"

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        return [
            RawJobCandidate(
                title=f"{query} Intern",
                company="Example Careers",
                location=location,
                source_url="https://career.example.com/job/view/id/1",
                source_provider="fake",
                snippet="Public listing snippet.",
                raw_description="Detailed public job description.",
                discovery_query=query,
                discovery_rank=1,
                detail_status="detail_fetched",
            )
        ][:limit]


def test_resolve_smoke_query_prefers_explicit_query() -> None:
    assert resolve_smoke_query("brand marketing", "https://example.com/?title=ignored") == "brand marketing"


def test_resolve_smoke_query_extracts_cuhksz_title_param() -> None:
    url = "https://career.cuhk.edu.cn/job/search?title=%E7%AE%97%E6%B3%95&title_type=1"

    assert resolve_smoke_query(None, url) == "算法"


def test_run_smoke_check_uses_provider_interface_without_network() -> None:
    result = run_smoke_check(
        provider=FakeProvider(),
        provider_name="fake",
        query="algorithm",
        location="Shenzhen",
        limit=3,
        min_candidates=1,
        require_detail=True,
    )

    assert result["passed"] is True
    assert result["candidate_count"] == 1
    assert result["candidate_with_url_count"] == 1
    assert result["candidate_with_detail_count"] == 1
    assert result["source_stats"][0]["source_provider"] == "fake"
    json.dumps(result, ensure_ascii=False)


def test_run_smoke_check_fails_when_detail_is_required_but_absent() -> None:
    class NoDetailProvider(FakeProvider):
        def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
            candidate = super().search_jobs(query=query, location=location, limit=limit)[0]
            return [candidate.model_copy(update={"raw_description": None, "detail_status": "detail_failed"})]

    result = run_smoke_check(
        provider=NoDetailProvider(),
        provider_name="fake",
        query="algorithm",
        location=None,
        limit=3,
        min_candidates=1,
        require_detail=True,
    )

    assert result["passed"] is False
    assert "No candidate included detail/raw_description content." in result["errors"]


def test_render_markdown_contains_candidate_links_and_counts() -> None:
    payload = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "input_url": "https://career.example.com/job/search?title=algorithm",
        "provider": "fake",
        "query": "algorithm",
        "location": None,
        "passed": True,
        "errors": [],
        "candidate_count": 1,
        "candidate_with_url_count": 1,
        "candidate_with_detail_count": 1,
        "source_stats": [
            {
                "source_provider": "fake",
                "raw_candidate_count": 1,
                "deduped_candidate_count": 1,
                "missing_url_count": 0,
                "missing_detail_count": 0,
                "detail_coverage_rate": 1.0,
                "warning_count": 0,
            }
        ],
        "candidates": [
            {
                "title": "Algorithm Intern",
                "company": "Example Careers",
                "location": "Shenzhen",
                "source_url": "https://career.example.com/job/view/id/1",
                "detail_status": "detail_fetched",
                "raw_description_length": 120,
            }
        ],
    }

    markdown = render_markdown(payload)

    assert "Provider Live Smoke Check" in markdown
    assert "Candidates: 1" in markdown
    assert "[open](https://career.example.com/job/view/id/1)" in markdown
