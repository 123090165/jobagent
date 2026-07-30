"""定义搜索质量样例、候选标注、脚本化 Provider 响应、指标值和报告契约。"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator


EVALUATOR_ONLY_KEYS = {
    "candidate_judgments",
    "detail_available",
    "duplicate_cluster_id",
    "duplicate_status",
    "reachable_candidate_ids",
    "relevance_grade",
    "stale_status",
    "strict_constraint_status",
    "strict_violation_codes",
    "strict_violation_evidence",
    "annotation_rationale",
    "candidate_payloads",
}


def _find_reserved_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in EVALUATOR_ONLY_KEYS:
                return str(key)
            found = _find_reserved_key(nested)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found = _find_reserved_key(nested)
            if found:
                return found
    return None


def _find_non_finite_float(value: object, path: str = "system_input") -> str | None:
    if isinstance(value, float) and not math.isfinite(value):
        return path
    if isinstance(value, dict):
        for key, nested in value.items():
            found = _find_non_finite_float(nested, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found = _find_non_finite_float(nested, f"{path}[{index}]")
            if found:
                return found
    return None


class CandidateJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_id: str = Field(min_length=1)
    canonical_identity: str = Field(min_length=1)
    relevance_grade: Literal[0, 1, 2, 3]
    strict_constraint_status: Literal["satisfied", "violated", "unknown"]
    strict_violation_codes: tuple[str, ...] = ()
    strict_violation_evidence: tuple[str, ...] = ()
    duplicate_cluster_id: str | None = None
    duplicate_status: Literal["confirmed", "suspected", "none"] = "none"
    stale_status: Literal["fresh", "stale", "unknown"] = "unknown"
    detail_available: bool = False
    source: str = Field(min_length=1)
    location: str | None = None
    annotation_rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_violation(self):
        if self.strict_constraint_status == "violated" and not self.strict_violation_evidence:
            raise ValueError("strict violations require explicit evidence")
        if self.duplicate_status == "confirmed" and not self.duplicate_cluster_id:
            raise ValueError("confirmed duplicate requires cluster ID")
        if self.duplicate_status != "confirmed" and self.duplicate_cluster_id:
            raise ValueError("only confirmed duplicates may set cluster ID")
        return self

    @property
    def cluster_id(self) -> str:
        return self.duplicate_cluster_id if self.duplicate_status == "confirmed" else self.candidate_id


class ScriptedProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    query: str = Field(min_length=1)
    location: str | None = None
    candidate_ids: frozenset[str] = frozenset()
    error_code: str | None = None

    @property
    def key(self) -> tuple[str, str, str | None]:
        return (self.source, self.query, self.location)

    @model_validator(mode="after")
    def validate_failure_response(self):
        if self.error_code and self.candidate_ids:
            raise ValueError("failed scripted responses cannot return candidates")
        return self


class CandidatePayload(BaseModel):
    """Versioned evaluator payload; replay converts it explicitly to RawJobCandidate."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_id: str = Field(min_length=1)
    title: str | None = None
    company: str | None = None
    location: str | None = None
    source_url: str | None = None
    source_provider: str = Field(min_length=1)
    snippet: str = ""
    raw_description: str | None = None
    discovery_query: str | None = None
    discovery_rank: int | None = None
    detail_status: str | None = None
    provider_warnings: tuple[str, ...] = ()


class EvaluationCase(BaseModel):
    """Evaluator input; labels are intentionally kept separate from system_input."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str = Field(min_length=1)
    fixture_version: str = Field(min_length=1)
    tags: dict[str, str] = Field(default_factory=dict)
    system_input: dict[str, JsonValue] = Field(default_factory=dict)
    selected_sources: frozenset[str] = Field(min_length=1)
    allowed_locations: frozenset[str] = frozenset()
    candidate_judgments: tuple[CandidateJudgment, ...] = ()
    scripted_responses: tuple[ScriptedProviderResponse, ...] = ()
    candidate_payloads: tuple[CandidatePayload, ...] = ()

    @model_validator(mode="after")
    def validate_refs(self):
        """验证候选、脚本响应和期望结果之间的引用完整性。"""
        ids = [c.candidate_id for c in self.candidate_judgments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate candidate evaluator IDs")
        known = set(ids)
        payload_ids = [p.candidate_id for p in self.candidate_payloads]
        if self.candidate_payloads and set(payload_ids) != known:
            raise ValueError("candidate payload/judgment IDs must match")
        if len(payload_ids) != len(set(payload_ids)):
            raise ValueError("duplicate candidate payload IDs")
        if self.candidate_payloads:
            judgments = self.judgment_map()
            for payload in self.candidate_payloads:
                if payload.source_provider != judgments[payload.candidate_id].source:
                    raise ValueError(
                        f"candidate {payload.candidate_id} payload source does not match judgment"
                    )
        reserved_key = _find_reserved_key(self.system_input)
        if reserved_key:
            raise ValueError(f"system_input contains evaluator-only key: {reserved_key}")
        non_finite_path = _find_non_finite_float(self.system_input)
        if non_finite_path:
            raise ValueError(f"system_input contains non-finite float at {non_finite_path}")
        response_keys = [response.key for response in self.scripted_responses]
        if len(response_keys) != len(set(response_keys)):
            raise ValueError("duplicate scripted provider response keys")
        for response in self.scripted_responses:
            dangling = response.candidate_ids - known
            if dangling:
                raise ValueError(
                    f"dangling scripted response candidate references: {sorted(dangling)}"
                )
            for candidate_id in response.candidate_ids:
                candidate = self.judgment_map()[candidate_id]
                if candidate.source != response.source:
                    raise ValueError(
                        f"candidate {candidate_id} source does not match scripted response"
                    )
        return self

    @property
    def reachable_candidate_ids(self) -> frozenset[str]:
        """计算当前来源和地点约束下脚本 Provider 实际可召回的候选集合。"""
        candidate_ids: set[str] = set()
        for response in self.scripted_responses:
            if response.source not in self.selected_sources:
                continue
            if self.allowed_locations and response.location not in self.allowed_locations:
                continue
            candidate_ids.update(response.candidate_ids)
        return frozenset(candidate_ids)

    def judgment_map(self) -> dict[str, CandidateJudgment]:
        """按 candidate_id 构建人工判断索引。"""
        return {c.candidate_id: c for c in self.candidate_judgments}

    def payload_map(self) -> dict[str, CandidatePayload]:
        """按 candidate_id 构建候选输入索引。"""
        return {c.candidate_id: c for c in self.candidate_payloads}

    def lookup_scripted(self, *, source: str, query: str, location: str | None) -> ScriptedProviderResponse:
        """精确查找预声明响应，禁止离线评估隐式访问网络。"""
        key = (source, query, location)
        for response in self.scripted_responses:
            if response.key == key:
                return response
        raise KeyError(f"undeclared scripted key: {key!r}")

    def system_projection(self) -> dict[str, Any]:
        """Return only system-owned input, never evaluator labels."""
        validated = TypeAdapter(dict[str, JsonValue]).validate_python(self.system_input)
        reserved_key = _find_reserved_key(validated)
        if reserved_key:
            raise ValueError(f"system_input contains evaluator-only key: {reserved_key}")
        non_finite_path = _find_non_finite_float(validated)
        if non_finite_path:
            raise ValueError(f"system_input contains non-finite float at {non_finite_path}")
        return deepcopy(validated)


class FixtureCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    corpus_version: str = Field(min_length=1)
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cases(self):
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case IDs")
        if any(case.fixture_version != self.corpus_version for case in self.cases):
            raise ValueError("case fixture_version must match corpus_version")
        return self


class MetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    numerator: float
    denominator: float
    value: float

    @model_validator(mode="after")
    def consistent(self):
        if any(not math.isfinite(x) for x in (self.numerator, self.denominator, self.value)):
            raise ValueError("metric values must be finite")
        if self.denominator < 0 or self.numerator < 0 or self.value < 0:
            raise ValueError("metric counts must be non-negative")
        if self.numerator > self.denominator or self.value > 1:
            raise ValueError("proportion metrics cannot exceed 1")
        expected = self.numerator / self.denominator if self.denominator else 0.0
        if abs(self.value - expected) > 1e-9:
            raise ValueError("inconsistent metric value (tolerance 1e-9)")
        if self.denominator == 0 and self.numerator != 0:
            raise ValueError("zero denominator requires zero numerator")
        if self.denominator == 0 and self.value != 0:
            raise ValueError("zero denominator metrics must have value 0")
        return self


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = Field(default="search_quality_v2", min_length=1)
    baseline_id: str = Field(min_length=1)
    fixture_version: str = Field(min_length=1)
    execution_mode: Literal["offline_replay", "live_calibration"]
    fixture_digest: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    python_version: str = Field(min_length=1)
    runtime_profile: str = Field(min_length=1)
    configuration: dict[str, Any]
    case_count: int = Field(ge=0)
    labelled_cluster_count: int = Field(ge=0)
    per_case: dict[str, dict[str, MetricValue]] = Field(default_factory=dict)
    macro_aggregates: dict[str, MetricValue] = Field(default_factory=dict)
    micro_aggregates: dict[str, MetricValue] = Field(default_factory=dict)
    budget_observations: dict[str, Any] = Field(default_factory=dict)
    measurement_notes: list[str] = Field(default_factory=list)
