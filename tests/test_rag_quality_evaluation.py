"""回归验证rag quality evaluation的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from pathlib import Path

from experiments.rag_quality.evaluator import (
    evaluate_rankings,
    lexical_rankings,
    load_corpus,
)
from scripts.evaluate_rag_quality import DEFAULT_FIXTURE, parse_args


def test_private_rag_fixture_is_valid_and_lexical_baseline_is_reproducible() -> None:
    corpus = load_corpus(DEFAULT_FIXTURE)

    report = evaluate_rankings(
        corpus,
        rankings=lexical_rankings(corpus),
        mode="lexical",
    )

    assert report.case_count == 4
    assert report.hit_rate == 1.0
    assert report.mean_recall_at_k == 1.0
    assert report.forbidden_hit_count == 0


def test_rag_quality_metrics_detect_forbidden_and_missing_results() -> None:
    corpus = load_corpus(DEFAULT_FIXTURE)
    rankings = lexical_rankings(corpus)
    rankings["saved-kubernetes"] = ["other-user-kubernetes"]
    rankings["resume-vector-rag"] = []

    report = evaluate_rankings(corpus, rankings=rankings, mode="test")

    assert report.hit_rate == 0.5
    assert report.forbidden_hit_count == 1
    by_case = {case.case_id: case for case in report.cases}
    assert by_case["saved-kubernetes"].forbidden_hits == [
        "other-user-kubernetes"
    ]
    assert by_case["resume-vector-rag"].reciprocal_rank == 0.0


def test_rag_quality_cli_defaults_to_network_free_fixture() -> None:
    args = parse_args([])

    assert args.mode == "lexical"
    assert isinstance(args.fixture, Path)
    assert args.fixture == DEFAULT_FIXTURE
    assert args.min_hit_rate == 1.0
    assert args.min_mrr == 0.75
