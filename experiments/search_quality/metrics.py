from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence

from .schemas import CandidateJudgment, EvaluationCase, MetricValue


def _mv(n: float, d: float) -> MetricValue:
    return MetricValue(numerator=n, denominator=d, value=(n / d if d else 0.0))


def _map(case: EvaluationCase) -> dict[str, CandidateJudgment]:
    return case.judgment_map()


def _validate_candidate_ids(
    case: EvaluationCase,
    candidate_ids: Iterable[str],
    *,
    label: str,
) -> list[str]:
    items = list(candidate_ids)
    if len(items) != len(set(items)):
        raise ValueError(f"duplicate {label} candidate references")
    invalid = set(items) - case.reachable_candidate_ids
    if invalid:
        raise ValueError(f"unknown or unreachable {label} candidate references: {sorted(invalid)}")
    return items


def validate_top_k(case: EvaluationCase, top_ids: Sequence[str]) -> None:
    """Reject Top-K references outside the declared reachable universe."""
    _validate_candidate_ids(case, top_ids, label="Top-K")


def _reachable(case: EvaluationCase) -> list[CandidateJudgment]:
    m = _map(case)
    return [m[i] for i in case.reachable_candidate_ids]


def _clusters(case: EvaluationCase) -> dict[str, list[CandidateJudgment]]:
    groups: defaultdict[str, list[CandidateJudgment]] = defaultdict(list)
    for candidate in _reachable(case):
        groups[candidate.cluster_id].append(candidate)
    return groups


def _eligible_cluster_grades(case: EvaluationCase) -> dict[str, int]:
    return {
        cluster_id: max(candidate.relevance_grade for candidate in candidates)
        for cluster_id, candidates in _clusters(case).items()
        if any(
            candidate.relevance_grade > 0
            and candidate.strict_constraint_status != "violated"
            for candidate in candidates
        )
    }


def pool_recall(case: EvaluationCase, pool_ids: Iterable[str]) -> MetricValue:
    validated_ids = _validate_candidate_ids(case, pool_ids, label="pool")
    judgments = _map(case)
    universe = _clusters(case)
    relevant = {
        cluster_id
        for cluster_id, candidates in universe.items()
        if max(candidate.relevance_grade for candidate in candidates) > 0
    }
    found = {
        judgments[candidate_id].cluster_id
        for candidate_id in validated_ids
        if judgments[candidate_id].cluster_id in relevant
    }
    return _mv(len(found), len(relevant))


def eligible_pool_recall(case: EvaluationCase, pool_ids: Iterable[str]) -> MetricValue:
    validated_ids = _validate_candidate_ids(case, pool_ids, label="pool")
    universe = set(_eligible_cluster_grades(case))
    judgments = _map(case)
    found = {
        judgments[candidate_id].cluster_id
        for candidate_id in validated_ids
        if judgments[candidate_id].cluster_id in universe
        and judgments[candidate_id].strict_constraint_status != "violated"
    }
    return _mv(len(found), len(universe))


def mixed_constraint_cluster_count(case: EvaluationCase) -> MetricValue:
    groups = _clusters(case)
    mixed = sum(
        1
        for candidates in groups.values()
        if any(candidate.strict_constraint_status == "violated" for candidate in candidates)
        and any(candidate.strict_constraint_status != "violated" for candidate in candidates)
    )
    return _mv(mixed, len(groups))


def precision_at_5(case: EvaluationCase, top_ids: Sequence[str]) -> MetricValue:
    shown = _validate_candidate_ids(case, list(top_ids)[:5], label="Top-K")
    judgments = _map(case)
    good = sum(
        1
        for candidate_id in shown
        if judgments[candidate_id].relevance_grade > 0
        and judgments[candidate_id].strict_constraint_status != "violated"
    )
    return _mv(good, 5)


def filled_slots_at_5(top_ids: Sequence[str]) -> MetricValue:
    return _mv(len(list(top_ids)[:5]), 5)


def ndcg_at_5(case: EvaluationCase, top_ids: Sequence[str]) -> MetricValue:
    shown = _validate_candidate_ids(case, list(top_ids)[:5], label="Top-K")
    judgments = _map(case)
    eligible = _eligible_cluster_grades(case)
    seen: set[str] = set()
    gains: list[float] = []
    for candidate_id in shown:
        candidate = judgments[candidate_id]
        gain = 0.0
        if (
            candidate.strict_constraint_status != "violated"
            and candidate.cluster_id in eligible
            and candidate.cluster_id not in seen
        ):
            seen.add(candidate.cluster_id)
            gain = float(2 ** eligible[candidate.cluster_id] - 1)
        gains.append(gain)
    dcg = sum(g / math.log2(rank + 2) for rank, g in enumerate(gains))
    ideal = sorted((2**grade - 1 for grade in eligible.values()), reverse=True)[:5]
    idcg = sum(g / math.log2(rank + 2) for rank, g in enumerate(ideal))
    return _mv(dcg, idcg)


def constraint_violation_at_5(case: EvaluationCase, top_ids: Sequence[str]) -> MetricValue:
    shown = _validate_candidate_ids(case, list(top_ids)[:5], label="Top-K")
    judgments = _map(case)
    violations = sum(
        1
        for candidate_id in shown
        if judgments[candidate_id].strict_constraint_status == "violated"
    )
    return _mv(violations, len(shown))


def duplicate_at_5(case: EvaluationCase, top_ids: Sequence[str]) -> MetricValue:
    shown = _validate_candidate_ids(case, list(top_ids)[:5], label="Top-K")
    judgments = _map(case)
    seen: set[str] = set()
    extra = 0
    for candidate_id in shown:
        candidate = judgments[candidate_id]
        if candidate.duplicate_status != "confirmed":
            continue
        if candidate.cluster_id in seen:
            extra += 1
        else:
            seen.add(candidate.cluster_id)
    return _mv(extra, len(shown))


def suspected_duplicate_at_5(case: EvaluationCase, top_ids: Sequence[str]) -> MetricValue:
    shown = _validate_candidate_ids(case, list(top_ids)[:5], label="Top-K")
    judgments = _map(case)
    suspected = sum(
        1 for candidate_id in shown if judgments[candidate_id].duplicate_status == "suspected"
    )
    return _mv(suspected, len(shown))


def detail_coverage(case: EvaluationCase, candidate_ids: Iterable[str]) -> MetricValue:
    validated_ids = _validate_candidate_ids(case, candidate_ids, label="final-scoring")
    judgments = _map(case)
    detailed = sum(1 for candidate_id in validated_ids if judgments[candidate_id].detail_available)
    return _mv(detailed, len(validated_ids))
