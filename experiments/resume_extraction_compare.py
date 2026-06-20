from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from app.agents.resume_parse_agent import parse_resume
from app.services.llm_provider import DEFAULT_DEEPSEEK_BASE_URL, DEFAULT_DEEPSEEK_MODEL
from app.services.llm_service import LLMConfig, LLMService, LLMServiceError
from tests.fixtures.resumes.profile_review_quality_cases import (
    PROFILE_REVIEW_QUALITY_CASES,
    ProfileReviewQualityCase,
)


MODES = ["direct_one_shot", "direct_fieldwise", "guided_reconciliation"]
FIELD_GROUPS = [
    ("identity", "identity, name, and target roles"),
    ("education", "education entries"),
    ("skills", "skills only"),
    ("work_experiences", "work, internship, research, or assistant experience"),
    ("projects", "projects only"),
    ("achievements", "achievements, certificates, highlights, and missing information"),
]

SHARED_SCHEMA_EXAMPLE = {
    "resume_profile": {
        "name": None,
        "target_roles": [],
        "education": [],
        "skills": [],
        "projects": [],
        "work_experiences": [],
        "certificates": [],
        "highlights": [],
        "missing_info": [],
    },
    "evidence": {
        "target_roles": [],
        "education": [],
        "skills": [],
        "projects": [],
        "work_experiences": [],
        "certificates": [],
        "highlights": [],
    },
    "quality_warnings": [],
}


@dataclass
class EvidenceValidation:
    evidence_valid: bool
    unsupported_count: int
    errors: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    mode: str
    run_index: int
    schema_valid: bool
    output: dict[str, Any]
    evidence_validation: EvidenceValidation
    coverage: dict[str, Any]
    elapsed_seconds: float
    request_count: int
    call_errors: list[str] = field(default_factory=list)
    model_warnings: list[str] = field(default_factory=list)


class ExperimentEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: StrictStr
    quote: StrictStr


class ExperimentEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    target_roles: list[ExperimentEvidenceItem]
    education: list[ExperimentEvidenceItem]
    skills: list[ExperimentEvidenceItem]
    projects: list[ExperimentEvidenceItem]
    work_experiences: list[ExperimentEvidenceItem]
    certificates: list[ExperimentEvidenceItem]
    highlights: list[ExperimentEvidenceItem]


class ExperimentResumeProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: StrictStr | None
    target_roles: list[Any]
    education: list[Any]
    skills: list[Any]
    projects: list[Any]
    work_experiences: list[Any]
    certificates: list[Any]
    highlights: list[Any]
    missing_info: list[Any]


class ExperimentOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    resume_profile: ExperimentResumeProfile
    evidence: ExperimentEvidence
    quality_warnings: list[Any]


def parse_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"DeepSeek env file not found: {env_path}")

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def build_deepseek_service(env_values: dict[str, str]) -> LLMService:
    api_key = env_values.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DeepSeek configuration is missing DEEPSEEK_API_KEY.")

    config = LLMConfig(
        api_key=api_key,
        base_url=env_values.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
        model=env_values.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        timeout_seconds=parse_float(
            env_values.get("JOBAGENT_LLM_TIMEOUT"),
            300.0,
        ),
        temperature=parse_float(
            env_values.get("JOBAGENT_LLM_TEMPERATURE"),
            0.0,
        ),
    )
    return LLMService(config)


def parse_float(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def base_system_prompt() -> str:
    schema_json = json.dumps(SHARED_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2)
    return (
        "You are a source-grounded resume extraction system. Return JSON only. "
        "Use the raw resume text as the only source of truth. Do not fabricate schools, "
        "employers, projects, skills, certificates, metrics, or target roles. If a fact "
        "is uncertain, leave the final field empty and add a warning or missing_info item. "
        "Every non-empty extracted school, employer, project, skill, certificate, and metric "
        "must include a verbatim source quote in the evidence section. Evidence quotes must "
        "be searchable in the raw resume text. Use this exact top-level schema:\n"
        f"{schema_json}"
    )


def run_direct_one_shot(service: LLMService, resume_text: str) -> dict[str, Any]:
    return service.chat_completion_json(
        system_prompt=base_system_prompt(),
        user_prompt=(
            "Mode: direct_one_shot.\n"
            "Extract the complete structured resume profile from this raw resume text.\n\n"
            f"Raw resume text:\n{resume_text}"
        ),
    )


def run_direct_fieldwise(service: LLMService, resume_text: str) -> tuple[dict[str, Any], list[str]]:
    fragments: dict[str, Any] = {}
    errors: list[str] = []
    for group_key, group_description in FIELD_GROUPS:
        try:
            fragments[group_key] = service.chat_completion_json(
                system_prompt=base_system_prompt(),
                user_prompt=(
                    "Mode: direct_fieldwise.\n"
                    f"Extract only this field group: {group_description}.\n"
                    "Return JSON with the shared schema. Leave unrelated fields empty.\n\n"
                    f"Raw resume text:\n{resume_text}"
                ),
            )
        except (LLMServiceError, ValueError, TypeError) as exc:
            errors.append(f"{group_key}: {sanitize_error(str(exc))}")

    try:
        merged = service.chat_completion_json(
            system_prompt=base_system_prompt(),
            user_prompt=(
                "Mode: direct_fieldwise merge.\n"
                "Merge the fieldwise fragments into one final shared-schema output. "
                "The raw resume remains the only source of truth. Reject unsupported fragment claims.\n\n"
                f"Raw resume text:\n{resume_text}\n\n"
                f"Fieldwise fragments JSON:\n{json.dumps(fragments, ensure_ascii=False)}\n\n"
                f"Fieldwise call errors:\n{json.dumps(errors, ensure_ascii=False)}"
            ),
        )
        return merged, errors
    except (LLMServiceError, ValueError, TypeError) as exc:
        errors.append(f"merge: {sanitize_error(str(exc))}")
        return {}, errors


def run_guided_reconciliation(service: LLMService, resume_text: str) -> dict[str, Any]:
    deterministic_profile = parse_resume(resume_text).model_dump(mode="json")
    return service.chat_completion_json(
        system_prompt=base_system_prompt(),
        user_prompt=(
            "Mode: guided_reconciliation.\n"
            "You receive raw resume text and deterministic parser output. The deterministic "
            "output is only a non-authoritative hint and may be incomplete or wrong. Verify "
            "every candidate against the raw source text. Correct, reject, merge, or supplement "
            "candidates only when supported by source evidence.\n\n"
            f"Raw resume text:\n{resume_text}\n\n"
            "Deterministic parser output JSON:\n"
            f"{json.dumps(deterministic_profile, ensure_ascii=False)}"
        ),
    )


def normalize_output(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    profile = payload.get("resume_profile")
    evidence = payload.get("evidence")
    normalized = json.loads(json.dumps(SHARED_SCHEMA_EXAMPLE))

    if isinstance(profile, dict):
        normalized_profile = normalized["resume_profile"]
        normalized_profile["name"] = _clean_optional_string(profile.get("name"))
        for key in [
            "target_roles",
            "education",
            "skills",
            "projects",
            "work_experiences",
            "certificates",
            "highlights",
            "missing_info",
        ]:
            normalized_profile[key] = _as_list(profile.get(key))

    if isinstance(evidence, dict):
        normalized_evidence = normalized["evidence"]
        for key in normalized_evidence:
            normalized_evidence[key] = [
                normalize_evidence_item(item) for item in _as_list(evidence.get(key))
            ]

    normalized["quality_warnings"] = _as_list(payload.get("quality_warnings"))
    return normalized


def is_schema_valid(payload: dict[str, Any] | None) -> bool:
    return validate_experiment_output(payload) == []


def validate_experiment_output(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return ["output must be a JSON object"]
    try:
        ExperimentOutput.model_validate(payload)
    except ValidationError as exc:
        return [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
    return []


def validate_evidence(output: dict[str, Any], resume_text: str) -> EvidenceValidation:
    required_values = collect_evidence_required_values(output)
    evidence_items = collect_evidence_items(output)
    errors: list[str] = []
    unsupported_count = 0

    malformed_errors = collect_malformed_evidence_errors(output)
    errors.extend(malformed_errors)
    unsupported_count += len(malformed_errors)

    for label, value, evidence_key in required_values:
        matching_items = [
            item
            for item in evidence_items.get(evidence_key, [])
            if value.lower() in item.get("value", "").lower()
            or value.lower() in item.get("quote", "").lower()
        ]
        if not matching_items:
            unsupported_count += 1
            errors.append(f"{label} missing evidence: {value}")
            continue
        if not any(item.get("quote", "") in resume_text for item in matching_items):
            unsupported_count += 1
            errors.append(f"{label} evidence quote not found in resume: {value}")

    for key, items in evidence_items.items():
        for item in items:
            quote = item.get("quote", "")
            if quote and quote not in resume_text:
                unsupported_count += 1
                errors.append(f"{key} evidence quote not found in resume: {quote[:80]}")

    return EvidenceValidation(
        evidence_valid=unsupported_count == 0,
        unsupported_count=unsupported_count,
        errors=errors,
    )


def collect_evidence_required_values(output: dict[str, Any]) -> list[tuple[str, str, str]]:
    profile = output.get("resume_profile", {})
    values: list[tuple[str, str, str]] = []
    for role in _as_list(profile.get("target_roles")):
        if isinstance(role, str) and role.strip():
            values.append(("target_role", role.strip(), "target_roles"))
    for skill in _as_list(profile.get("skills")):
        if isinstance(skill, str) and skill.strip():
            values.append(("skill", skill.strip(), "skills"))
    for cert in _as_list(profile.get("certificates")):
        if isinstance(cert, str) and cert.strip():
            values.append(("certificate", cert.strip(), "certificates"))
    for highlight in _as_list(profile.get("highlights")):
        if isinstance(highlight, str) and metric_pattern().search(highlight):
            values.append(("metric", metric_pattern().search(highlight).group(0), "highlights"))
    for item in _as_list(profile.get("education")):
        if isinstance(item, dict):
            school = _clean_optional_string(item.get("school"))
            if school:
                values.append(("school", school, "education"))
    for item in _as_list(profile.get("work_experiences")):
        if isinstance(item, dict):
            company = _clean_optional_string(item.get("company"))
            if company:
                values.append(("employer", company, "work_experiences"))
    for item in _as_list(profile.get("projects")):
        if isinstance(item, dict):
            name = _clean_optional_string(item.get("name"))
            if name:
                values.append(("project", name, "projects"))
    return values


def collect_evidence_items(output: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    evidence = output.get("evidence", {})
    result: dict[str, list[dict[str, str]]] = {}
    for key in SHARED_SCHEMA_EXAMPLE["evidence"]:
        result[key] = []
        for item in _as_list(evidence.get(key) if isinstance(evidence, dict) else []):
            if isinstance(item, dict):
                value = str(item.get("value") or "").strip()
                quote = str(item.get("quote") or "").strip()
            else:
                value = ""
                quote = ""
            if value or quote:
                result[key].append({"value": value, "quote": quote})
    return result


def normalize_evidence_item(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {"value": "", "quote": ""}
    return {
        "value": str(item.get("value") or "").strip(),
        "quote": str(item.get("quote") or "").strip(),
    }


def collect_malformed_evidence_errors(output: dict[str, Any]) -> list[str]:
    evidence = output.get("evidence", {})
    if not isinstance(evidence, dict):
        return ["evidence must be an object"]
    errors: list[str] = []
    for key in SHARED_SCHEMA_EXAMPLE["evidence"]:
        raw_items = evidence.get(key, [])
        if not isinstance(raw_items, list):
            errors.append(f"{key} evidence must be a list")
            continue
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                errors.append(f"{key}[{index}] evidence must use value/quote object")
                continue
            if set(item.keys()) != {"value", "quote"}:
                errors.append(f"{key}[{index}] evidence must contain only value and quote")
            if not isinstance(item.get("value"), str) or not isinstance(item.get("quote"), str):
                errors.append(f"{key}[{index}] evidence value and quote must be strings")
    return errors


def evaluate_coverage(
    output: dict[str, Any],
    case: ProfileReviewQualityCase | None,
) -> dict[str, Any]:
    if case is None:
        return {"available": False}
    profile = output.get("resume_profile", {})
    skills_text = " ".join(str(item) for item in _as_list(profile.get("skills")))
    projects_text = json.dumps(profile.get("projects", []), ensure_ascii=False)
    work_text = json.dumps(profile.get("work_experiences", []), ensure_ascii=False)
    education_text = json.dumps(profile.get("education", []), ensure_ascii=False)
    return {
        "available": True,
        "skills": coverage_for_expected(skills_text, case.regression_skills or case.expected_skills),
        "projects": coverage_for_expected(projects_text, case.regression_project_keywords),
        "work_experiences": coverage_for_expected(work_text, case.regression_work_keywords),
        "education": coverage_for_expected(education_text, case.regression_education_keywords),
    }


def coverage_for_expected(text: str, expected: list[str]) -> dict[str, Any]:
    lowered = text.lower()
    found = [item for item in expected if item.lower() in lowered]
    missing = [item for item in expected if item.lower() not in lowered]
    total = len(expected)
    return {
        "expected": expected,
        "found": found,
        "missing": missing,
        "rate": 1.0 if total == 0 else len(found) / total,
    }


def aggregate_report(results: list[RunResult]) -> dict[str, Any]:
    by_mode: dict[str, list[RunResult]] = {}
    for result in results:
        by_mode.setdefault(result.mode, []).append(result)

    mode_summaries: dict[str, Any] = {}
    for mode, mode_results in by_mode.items():
        total = len(mode_results)
        schema_valid = sum(1 for result in mode_results if result.schema_valid)
        evidence_valid = sum(1 for result in mode_results if result.evidence_validation.evidence_valid)
        unsupported_count = sum(
            result.evidence_validation.unsupported_count for result in mode_results
        )
        elapsed_values = [result.elapsed_seconds for result in mode_results]
        request_counts = [result.request_count for result in mode_results]
        mode_summaries[mode] = {
            "runs": total,
            "schema_valid_rate": safe_rate(schema_valid, total),
            "evidence_valid_rate": safe_rate(evidence_valid, total),
            "unsupported_field_count": unsupported_count,
            "stability": calculate_stability([result.output for result in mode_results]),
            "average_elapsed_seconds": (
                sum(elapsed_values) / len(elapsed_values) if elapsed_values else 0.0
            ),
            "average_request_count": (
                sum(request_counts) / len(request_counts) if request_counts else 0.0
            ),
            "call_error_count": sum(len(result.call_errors) for result in mode_results),
            "model_warning_count": sum(len(result.model_warnings) for result in mode_results),
            "coverage": aggregate_coverage([result.coverage for result in mode_results]),
        }
    return mode_summaries


def aggregate_coverage(coverages: list[dict[str, Any]]) -> dict[str, float]:
    rates: dict[str, list[float]] = {}
    for coverage in coverages:
        if not coverage.get("available"):
            continue
        for key in ["skills", "projects", "work_experiences", "education"]:
            value = coverage.get(key)
            if isinstance(value, dict):
                rates.setdefault(key, []).append(float(value.get("rate", 0.0)))
    return {
        key: sum(values) / len(values)
        for key, values in rates.items()
        if values
    }


def calculate_stability(outputs: list[dict[str, Any]]) -> float:
    if len(outputs) < 2:
        return 1.0
    scores: list[float] = []
    for left, right in combinations(outputs, 2):
        scores.append(jaccard(stability_tokens(left), stability_tokens(right)))
    return sum(scores) / len(scores) if scores else 1.0


def stability_tokens(output: dict[str, Any]) -> set[str]:
    profile = output.get("resume_profile", {})
    tokens: set[str] = set()
    for key in ["target_roles", "skills", "certificates", "highlights"]:
        tokens.update(str(item).lower() for item in _as_list(profile.get(key)) if str(item).strip())
    for key in ["education", "projects", "work_experiences"]:
        for item in _as_list(profile.get(key)):
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str) and value.strip():
                        tokens.add(value.strip().lower())
                    elif isinstance(value, list):
                        tokens.update(str(child).lower() for child in value if str(child).strip())
    return tokens


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def safe_rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def run_experiment(
    *,
    service: LLMService,
    resume_text: str,
    case: ProfileReviewQualityCase | None,
    runs: int,
    modes: list[str],
) -> list[RunResult]:
    results: list[RunResult] = []
    for mode in modes:
        for run_index in range(1, runs + 1):
            payload: dict[str, Any] = {}
            errors: list[str] = []
            request_count = logical_request_count_for_mode(mode)
            started_at = time.perf_counter()
            try:
                if mode == "direct_one_shot":
                    payload = run_direct_one_shot(service, resume_text)
                elif mode == "direct_fieldwise":
                    payload, errors = run_direct_fieldwise(service, resume_text)
                elif mode == "guided_reconciliation":
                    payload = run_guided_reconciliation(service, resume_text)
                else:
                    raise ValueError(f"Unsupported mode: {mode}")
            except (LLMServiceError, ValueError, TypeError) as exc:
                errors.append(sanitize_error(str(exc)))
            elapsed_seconds = time.perf_counter() - started_at

            schema_valid = is_schema_valid(payload)
            evidence_validation = validate_evidence(
                payload if isinstance(payload, dict) else {},
                resume_text,
            )
            normalized = normalize_output(payload)
            results.append(
                RunResult(
                    mode=mode,
                    run_index=run_index,
                    schema_valid=schema_valid,
                    output=normalized,
                    evidence_validation=evidence_validation,
                    coverage=evaluate_coverage(normalized, case),
                    elapsed_seconds=elapsed_seconds,
                    request_count=request_count,
                    call_errors=errors,
                    model_warnings=[
                        str(item)
                        for item in _as_list(normalized.get("quality_warnings"))
                        if str(item).strip()
                    ],
                )
            )
    return results


def logical_request_count_for_mode(mode: str) -> int:
    if mode == "direct_fieldwise":
        return len(FIELD_GROUPS) + 1
    if mode in {"direct_one_shot", "guided_reconciliation"}:
        return 1
    return 0


def write_reports(
    *,
    output_dir: Path,
    input_label: str,
    results: list[RunResult],
    env_summary: dict[str, Any],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", input_label).strip("_") or "resume"
    json_path = output_dir / f"{timestamp}_{safe_label}_resume_extraction_compare.json"
    markdown_path = output_dir / f"{timestamp}_{safe_label}_resume_extraction_compare.md"
    summary = aggregate_report(results)
    report = {
        "created_at": timestamp,
        "input_label": input_label,
        "env_summary": env_summary,
        "mode_summary": summary,
        "runs": [serialize_run_result(result) for result in results],
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_summary(report), encoding="utf-8")
    return json_path, markdown_path


def serialize_run_result(result: RunResult) -> dict[str, Any]:
    return {
        "mode": result.mode,
        "run_index": result.run_index,
        "schema_valid": result.schema_valid,
        "evidence_valid": result.evidence_validation.evidence_valid,
        "unsupported_count": result.evidence_validation.unsupported_count,
        "elapsed_seconds": result.elapsed_seconds,
        "request_count": result.request_count,
        "evidence_errors": result.evidence_validation.errors,
        "coverage": result.coverage,
        "call_errors": result.call_errors,
        "model_warnings": result.model_warnings,
        "output": result.output,
    }


def render_markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "# Resume Extraction Comparison",
        "",
        f"- Created at: `{report['created_at']}`",
        f"- Input: `{report['input_label']}`",
        f"- Provider: `{report['env_summary'].get('provider')}`",
        f"- Model: `{report['env_summary'].get('model')}`",
        "",
        "## Mode Summary",
        "",
        "| Mode | Runs | Schema Valid | Evidence Valid | Unsupported Fields | Stability | Avg Seconds | Avg Requests | Call Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in report["mode_summary"].items():
        lines.append(
            "| {mode} | {runs} | {schema:.2f} | {evidence:.2f} | {unsupported} | {stability:.2f} | {seconds:.2f} | {requests:.2f} | {errors} |".format(
                mode=mode,
                runs=summary["runs"],
                schema=summary["schema_valid_rate"],
                evidence=summary["evidence_valid_rate"],
                unsupported=summary["unsupported_field_count"],
                stability=summary["stability"],
                seconds=summary["average_elapsed_seconds"],
                requests=summary["average_request_count"],
                errors=summary["call_error_count"],
            )
        )
    lines.extend(["", "## Coverage", ""])
    for mode, summary in report["mode_summary"].items():
        lines.append(f"### {mode}")
        coverage = summary.get("coverage", {})
        if not coverage:
            lines.append("- No fixture expectations available.")
            continue
        for key, value in coverage.items():
            lines.append(f"- {key}: {value:.2f}")
    lines.append("")
    return "\n".join(lines)


def sanitize_error(message: str) -> str:
    text = message.strip() or "unknown error"
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [masked]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(?i)(DEEPSEEK_API_KEY|JOBAGENT_LLM_API_KEY|api[_-]?key|token|secret)\s*[:=]\s*['\"]?[^'\"\s,;]+",
        r"\1=[masked]",
        text,
    )
    text = re.sub(r"\b(sk-[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{32,})\b", "[masked]", text)
    return text


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def metric_pattern() -> re.Pattern[str]:
    return re.compile(
        r"(\d+(?:\.\d+)?\s?%|\d+\s?(?:ms|s|APIs?|tests?|users?|samples?|cases?|clips?)|[0-9]+k)",
        re.IGNORECASE,
    )


def load_input(args: argparse.Namespace) -> tuple[str, str, ProfileReviewQualityCase | None]:
    if args.case_id and args.input_file:
        raise ValueError("Use either --case-id or --input-file, not both.")
    if not args.case_id and not args.input_file:
        raise ValueError("Provide --case-id or --input-file.")
    if args.case_id:
        for case in PROFILE_REVIEW_QUALITY_CASES:
            if case.case_id == args.case_id:
                return case.resume_text, case.case_id, case
        available = ", ".join(case.case_id for case in PROFILE_REVIEW_QUALITY_CASES)
        raise ValueError(f"Unknown case id: {args.case_id}. Available: {available}")
    input_path = Path(args.input_file)
    return input_path.read_text(encoding="utf-8"), input_path.stem, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id")
    parser.add_argument("--input-file")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--env-file", default=".env.deepseek.local")
    parser.add_argument("--output-dir", default="experiments/output")
    parser.add_argument("--mode", choices=MODES, action="append")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be at least 1")

    env_values = parse_env_file(args.env_file)
    service = build_deepseek_service(env_values)
    resume_text, input_label, case = load_input(args)
    modes = args.mode or MODES
    results = run_experiment(
        service=service,
        resume_text=resume_text,
        case=case,
        runs=args.runs,
        modes=modes,
    )
    json_path, markdown_path = write_reports(
        output_dir=Path(args.output_dir),
        input_label=input_label,
        results=results,
        env_summary={
            "provider": "deepseek",
            "base_url": env_values.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
            "model": env_values.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
            "temperature": parse_float(env_values.get("JOBAGENT_LLM_TEMPERATURE"), 0.0),
        },
    )
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown summary: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
