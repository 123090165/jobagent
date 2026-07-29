from __future__ import annotations

from types import SimpleNamespace

from app.application.job_search_usecases import _assemble_results
from app.schemas.job import JDRequirement
from app.services.job_search_execution.result_builder import _diversify_matched_items
from app.services.job_search_providers.base import RawJobCandidate


def _candidate(source_url: str, snippet: str) -> RawJobCandidate:
    return RawJobCandidate(
        title="Algorithm Intern",
        company="Example",
        location="Shenzhen",
        source_url=source_url,
        source_provider="boss_zhipin",
        snippet=snippet,
        raw_description=snippet,
        detail_status="browser_helper_payload",
    )


def _matched_item(candidate: RawJobCandidate, score: int) -> dict[str, object]:
    return {
        "candidate": candidate,
        "analysis": SimpleNamespace(
            raw_jd=candidate.raw_description,
            requirements=[
                JDRequirement(
                    category="skill",
                    name="algorithm",
                    necessity="required",
                    evidence_quote=candidate.raw_description,
                    confidence=0.9,
                )
            ],
        ),
        "analysis_mode": "deterministic",
        "match_score": score,
        "score_breakdown": {"total": score},
        "evidence_quotes": [],
        "matched_keywords": ["algorithm"],
        "match_reasons": ["Matched profile signals: algorithm."],
        "risks": [],
        "confidence_label": "strong" if score >= 85 else "weak",
    }


def test_assemble_results_dedupes_canonical_source_urls() -> None:
    first = _candidate(
        "https://www.zhipin.com/job_detail/ABC123.html?lid=first&securityId=one",
        "higher scored duplicate",
    )
    second = _candidate(
        "https://www.zhipin.com/job_detail/ABC123.html?lid=second&securityId=two",
        "lower scored duplicate",
    )

    results = _assemble_results(
        [_matched_item(first, 91), _matched_item(second, 55)],
        source="live_search",
    )

    assert len(results) == 1
    assert results[0].match_score == 91
    assert results[0].description == "higher scored duplicate"
    assert results[0].job_requirements[0].name == "algorithm"


def test_diversity_only_reorders_close_scores() -> None:
    first = _candidate("https://example.com/1", "first")
    second = _candidate("https://example.com/2", "second")
    different_company = _candidate("https://example.com/3", "third").model_copy(
        update={"company": "Different", "source_provider": "linkedin"}
    )
    distant = _candidate("https://example.com/4", "fourth").model_copy(
        update={"company": "Distant", "source_provider": "remoteok"}
    )

    diversified = _diversify_matched_items(
        [
            _matched_item(first, 90),
            _matched_item(second, 89),
            _matched_item(different_company, 88),
            _matched_item(distant, 70),
        ]
    )

    assert [item["candidate"].company for item in diversified] == [
        "Example",
        "Different",
        "Example",
        "Distant",
    ]
