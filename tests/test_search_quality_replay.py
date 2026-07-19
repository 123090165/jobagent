from __future__ import annotations

import pytest

from app.services.job_search_providers.base import JobSearchProviderError
from experiments.search_quality.replay import ScriptedReplayProvider, load_corpus, run_replay


def test_scripted_provider_rejects_unplanned_query() -> None:
    case = load_corpus().cases[0]
    provider = ScriptedReplayProvider(case, allowed_queries=["AI ML internship"])

    with pytest.raises(JobSearchProviderError, match="undeclared scripted query"):
        provider.search_jobs(query="not planned", location="Remote", limit=5)


def test_offline_replay_is_deterministic_and_keeps_six_trace_steps() -> None:
    corpus = load_corpus()
    case_ids = {"technical_ai_intern", "cross_source_repost"}

    first = run_replay(corpus, case_ids=case_ids)
    second = run_replay(corpus, case_ids=case_ids)

    assert first == second
    assert first["manifest_digest"]
    assert all(len(case["trace_steps"]) == 6 for case in first["cases"])
    assert all(case["top_5_candidate_ids"] for case in first["cases"])
    assert all(
        case["metrics"]["constraint_violation_at_5"]["value"] == 0.0
        for case in first["cases"]
    )
    assert all(
        case["metrics"]["pool_recall"]["value"] == 1.0
        for case in first["cases"]
    )
    assert all(
        case["metrics"]["duplicate_at_5"]["value"] == 0.0
        for case in first["cases"]
    )
