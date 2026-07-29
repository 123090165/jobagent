from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import (
    RAGQualityCaseResult,
    RAGQualityCorpus,
    RAGQualityReport,
)


def load_corpus(path: Path) -> RAGQualityCorpus:
    return RAGQualityCorpus.model_validate_json(path.read_text(encoding="utf-8"))


def lexical_rankings(corpus: RAGQualityCorpus) -> dict[str, list[str]]:
    rankings: dict[str, list[str]] = {}
    for case in corpus.cases:
        query_terms = _terms(case.query)
        candidates = [
            document
            for document in corpus.documents
            if document.owner == "primary"
            and document.resource_type in case.resource_types
        ]
        scored = [
            (
                len(query_terms & _terms(document.searchable_text)),
                document.document_key,
            )
            for document in candidates
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        rankings[case.case_id] = [
            key for score, key in scored[: case.top_k] if score > 0
        ]
    return rankings


def evaluate_rankings(
    corpus: RAGQualityCorpus,
    *,
    rankings: dict[str, list[str]],
    mode: str,
    latencies_ms: dict[str, float] | None = None,
) -> RAGQualityReport:
    latencies_ms = latencies_ms or {}
    results: list[RAGQualityCaseResult] = []
    for case in corpus.cases:
        returned = list(dict.fromkeys(rankings.get(case.case_id, [])))[: case.top_k]
        expected = case.expected_document_keys
        found = expected & set(returned)
        first_rank = next(
            (
                index
                for index, document_key in enumerate(returned, start=1)
                if document_key in expected
            ),
            None,
        )
        results.append(
            RAGQualityCaseResult(
                case_id=case.case_id,
                returned_document_keys=returned,
                hit=bool(found),
                recall_at_k=len(found) / len(expected),
                precision_at_k=len(found) / case.top_k,
                reciprocal_rank=(1 / first_rank if first_rank else 0.0),
                forbidden_hits=[
                    key for key in returned if key in case.forbidden_document_keys
                ],
                latency_ms=max(0.0, latencies_ms.get(case.case_id, 0.0)),
            )
        )
    count = len(results)
    return RAGQualityReport(
        fixture_version=corpus.fixture_version,
        mode=mode,
        case_count=count,
        hit_rate=sum(result.hit for result in results) / count,
        mean_recall_at_k=sum(result.recall_at_k for result in results) / count,
        mean_precision_at_k=sum(result.precision_at_k for result in results) / count,
        mean_reciprocal_rank=(
            sum(result.reciprocal_rank for result in results) / count
        ),
        forbidden_hit_count=sum(len(result.forbidden_hits) for result in results),
        mean_latency_ms=sum(result.latency_ms for result in results) / count,
        cases=results,
    )


def write_report(report: RAGQualityReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _terms(value: str) -> set[str]:
    normalized = value.casefold()
    terms = set(re.findall(r"[a-z0-9+#.]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    terms.update(
        chinese[index : index + 2]
        for index in range(max(0, len(chinese) - 1))
    )
    return {term for term in terms if term}
