from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.application.job_search_usecases import preview_job_search_run
from app.config.env_loader import load_local_env
from app.main import app
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers import (
    AVAILABLE_JOB_SEARCH_SOURCES,
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
    encode_selected_sources,
    get_job_search_provider_status,
    normalize_job_search_provider_name,
    resolve_job_search_provider,
    selected_sources_from_provider_name,
)
from app.services.job_search_recall_metrics import (
    build_source_recall_stats,
    dedupe_recall_candidates,
)
from app.services.llm_service import LLMServiceError
from tests.fixtures.resumes.multidomain_flow_cases import (
    MULTIDOMAIN_FLOW_CASES,
    MultidomainFlowCase,
)


def main() -> int:
    args = parse_args()
    load_local_env(args.env_file)

    provider_name, selected_sources = resolve_provider_selection(args.provider, args.source)
    provider = resolve_job_search_provider(provider_name)
    provider_statuses = provider_status_snapshot(provider_name, selected_sources)
    missing_required = [
        status
        for status in provider_statuses
        if not status["configured"] and status["provider"] in {"serper_web", "linkedin"}
    ]
    if missing_required and normalize_job_search_provider_name(args.provider) in {"serper_web", "linkedin"}:
        print(
            "Provider is not configured: "
            + "; ".join(f"{item['provider']} - {item['reason']}" for item in missing_required),
            file=sys.stderr,
        )
        return 2

    cases = select_cases(args.case_id)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with tempfile.TemporaryDirectory(prefix="jobagent_provider_recall_", ignore_cleanup_errors=True) as temp_dir:
        os.environ["JOBAGENT_DB_PATH"] = str(Path(temp_dir) / "provider_recall.sqlite3")
        client = TestClient(app)
        try:
            results = [
                run_case(
                    client=client,
                    case=case,
                    provider=provider,
                    provider_name=provider_name,
                    selected_sources=selected_sources,
                    queries_per_case=args.queries_per_case,
                    limit_per_query=args.limit_per_query,
                    max_results=args.max_results,
                    include_location=not args.no_location,
                )
                for case in cases
            ]
        finally:
            client.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider_name,
        "selected_sources": selected_sources,
        "provider_statuses": provider_statuses,
        "queries_per_case": args.queries_per_case,
        "limit_per_query": args.limit_per_query,
        "max_results": args.max_results,
        "include_location": not args.no_location,
        "results": results,
    }
    json_path = output_dir / f"{timestamp}_provider_recall_calibration.json"
    markdown_path = output_dir / f"{timestamp}_provider_recall_calibration.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {markdown_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate job-search provider recall across resume domains.")
    parser.add_argument(
        "--env-file",
        default=".env.deepseek.local",
        help="Local env file. Serper-backed sources read SERPER_API_KEY or JOBAGENT_SERPER_API_KEY from it.",
    )
    parser.add_argument(
        "--provider",
        default="multi_source",
        choices=["multi_source", "cuhksz_career", "linkedin", "remoteok", "serper_web"],
        help="Provider to calibrate. multi_source uses --source values.",
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=AVAILABLE_JOB_SEARCH_SOURCES,
        default=[],
        help="Selected source for multi_source. Can be repeated. Defaults to all current frontend sources.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Limit to one or more multidomain fixture case ids. Defaults to all cases.",
    )
    parser.add_argument("--queries-per-case", type=int, default=2)
    parser.add_argument("--limit-per-query", type=int, default=5)
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--no-location", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "experiments" / "output"),
        help="Directory for JSON and Markdown reports.",
    )
    return parser.parse_args()


def resolve_provider_selection(provider: str, sources: list[str]) -> tuple[str, list[str]]:
    normalized = normalize_job_search_provider_name(provider)
    if normalized == "multi_source":
        selected = sources or list(AVAILABLE_JOB_SEARCH_SOURCES)
        return encode_selected_sources(selected), selected
    return normalized, selected_sources_from_provider_name(normalized)


def provider_status_snapshot(provider_name: str, selected_sources: list[str]) -> list[dict[str, object]]:
    statuses = [get_job_search_provider_status(provider_name)]
    for source in selected_sources:
        status = get_job_search_provider_status(source)
        if status not in statuses:
            statuses.append(status)
    return statuses


def run_case(
    *,
    client: TestClient,
    case: MultidomainFlowCase,
    provider: JobSearchProvider,
    provider_name: str,
    selected_sources: list[str],
    queries_per_case: int,
    limit_per_query: int,
    max_results: int,
    include_location: bool,
) -> dict[str, Any]:
    preview_bundle = build_preview_bundle(
        client,
        case,
        provider_name=provider_name,
        selected_sources=selected_sources,
        max_results=max_results,
    )
    confirmed = preview_bundle["confirmed"]
    preview = preview_bundle["preview"]
    provider_queries = select_provider_queries(preview, queries_per_case)
    location = (preview["locations"] or confirmed["preferred_locations"] or [None])[0] if include_location else None

    query_runs = [
        run_provider_query(provider, query=query, location=location, limit=limit_per_query)
        for query in provider_queries
    ]
    raw_candidates = [candidate for result in query_runs for candidate in result["candidates"]]
    deduped, duplicate_count, truncated_count = dedupe_recall_candidates(
        raw_candidates,
        limit=max_results * 2,
    )
    source_stats = build_source_recall_stats(raw_candidates, deduped)
    ranking_signals = preview["ranking_signals"] or preview["search_signal_terms"]
    annotated = [
        candidate_to_report_item(candidate, ranking_signals=ranking_signals)
        for candidate in deduped
    ]
    return {
        "case_id": case.case_id,
        "source_file": case.filename,
        "target_roles": confirmed["target_roles"],
        "target_directions": confirmed["target_directions"],
        "preferred_locations": confirmed["preferred_locations"],
        "provider": provider_name,
        "selected_sources": selected_sources,
        "provider_queries": provider_queries,
        "ranking_signals": ranking_signals,
        "provider_search_urls": preview["provider_search_urls"],
        "query_results": [
            {
                "query": result["query"],
                "location": result["location"],
                "returned_count": result["returned_count"],
                "error": result["error"],
            }
            for result in query_runs
        ],
        "raw_candidate_count": len(raw_candidates),
        "deduped_candidate_count": len(deduped),
        "duplicate_count": duplicate_count,
        "truncated_candidate_count": truncated_count,
        "missing_source_url_count": sum(1 for item in deduped if not item.source_url),
        "missing_detail_count": sum(item.missing_detail_count for item in source_stats),
        "source_provider_counts": dict(Counter(candidate.source_provider for candidate in deduped)),
        "source_stats": [item.to_dict() for item in source_stats],
        "top_candidates": annotated[:20],
    }


def build_preview_bundle(
    client: TestClient,
    case: MultidomainFlowCase,
    *,
    provider_name: str,
    selected_sources: list[str],
    max_results: int,
) -> dict[str, Any]:
    resume_text = case.path.read_text(encoding="utf-8")
    session = client.post("/api/v1/profile-sessions").json()
    session_id = session["session_id"]
    client.post(f"/api/v1/profile-sessions/{session_id}/resume-text", json={"text": resume_text})
    client.post(f"/api/v1/profile-sessions/{session_id}/parse-resume", params={"use_llm": False})
    draft = client.post(f"/api/v1/profile-sessions/{session_id}/profile-draft").json()["profile_draft"]
    confirmed = client.post(f"/api/v1/profile-drafts/{draft['profile_draft_id']}/confirm").json()[
        "confirmed_profile"
    ]
    preview = preview_job_search_run(
        JobSearchRunCreateRequest(
            session_id=session_id,
            search_mode="live_search",
            search_provider=provider_name,
            selected_sources=selected_sources,
            use_llm=False,
            max_results=max_results,
        ),
        llm_service=_DeterministicIntentFallbackLLM(),
    ).model_dump(mode="json")
    return {"confirmed": confirmed, "preview": preview}


class _DeterministicIntentFallbackLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise LLMServiceError("provider recall calibration uses deterministic search intent")


def run_provider_query(
    provider: JobSearchProvider,
    *,
    query: str,
    location: str | None,
    limit: int,
) -> dict[str, Any]:
    try:
        candidates = provider.search_jobs(query=query, location=location, limit=limit)
        error = None
    except JobSearchProviderError as exc:
        candidates = []
        error = f"{type(exc).__name__}: {exc}"
    return {
        "query": query,
        "location": location,
        "returned_count": len(candidates),
        "error": error,
        "candidates": candidates,
    }


def candidate_to_report_item(
    candidate: RawJobCandidate,
    *,
    ranking_signals: list[str],
) -> dict[str, Any]:
    text = " ".join(
        [
            candidate.title or "",
            candidate.company or "",
            candidate.location or "",
            candidate.snippet or "",
            candidate.raw_description or "",
        ]
    )
    return {
        "title": candidate.title,
        "company": candidate.company,
        "source_provider": candidate.source_provider,
        "domain": domain(candidate.source_url),
        "location": candidate.location,
        "source_url": candidate.source_url,
        "snippet": candidate.snippet,
        "discovery_query": candidate.discovery_query,
        "discovery_rank": candidate.discovery_rank,
        "detail_status": candidate.detail_status,
        "matched_signals": matched_signals(text, ranking_signals),
        "warnings": candidate.provider_warnings,
    }


def matched_signals(text: str, ranking_signals: list[str], *, limit: int = 8) -> list[str]:
    haystack = text.lower()
    matches: list[str] = []
    seen: set[str] = set()
    for signal in ranking_signals:
        item = str(signal).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        if key in haystack:
            seen.add(key)
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Provider Recall Calibration",
        "",
        f"Generated: {payload['generated_at']}",
        f"Provider: `{payload['provider']}`",
        f"Selected sources: {fmt(payload['selected_sources'])}",
        f"Queries per case: {payload['queries_per_case']}",
        f"Limit per query: {payload['limit_per_query']}",
        f"Max results: {payload['max_results']}",
        f"Location appended: {payload['include_location']}",
        "",
        "This report measures provider recall before final LLM ranking. It does not call DeepSeek and it does not build Job Brief.",
        "",
        "## Provider Status",
        "",
        "| Provider | Configured | Source kind | Detail strategy | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for status in payload["provider_statuses"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md(status["provider"]),
                    str(status["configured"]),
                    md(status["source_kind"]),
                    md(status["detail_strategy"]),
                    md(status.get("reason") or ""),
                ]
            )
            + " |"
        )
    for result in payload["results"]:
        lines.extend(
            [
                "",
                f"## {result['case_id']}",
                "",
                f"Source file: `{result['source_file']}`",
                f"- target_roles: {fmt(result['target_roles'])}",
                f"- target_directions: {fmt(result['target_directions'])}",
                f"- preferred_locations: {fmt(result['preferred_locations'])}",
                f"- raw candidates: {result['raw_candidate_count']}",
                f"- deduped candidates: {result['deduped_candidate_count']}",
                f"- duplicates: {result['duplicate_count']}",
                f"- truncated: {result['truncated_candidate_count']}",
                f"- missing source URLs: {result['missing_source_url_count']}",
                f"- missing details: {result['missing_detail_count']}",
                f"- source providers: {fmt_counts(result['source_provider_counts'])}",
                "",
                "### Source Stats",
                "",
                "| Source | Raw | Deduped | Unretained | Missing URL | Missing Detail | Detail Coverage | Warnings |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for stat in result["source_stats"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md(stat["source_provider"]),
                        str(stat["raw_candidate_count"]),
                        str(stat["deduped_candidate_count"]),
                        str(stat["unretained_candidate_count"]),
                        str(stat["missing_url_count"]),
                        str(stat["missing_detail_count"]),
                        str(stat["detail_coverage_rate"]),
                        str(stat["warning_count"]),
                    ]
                )
                + " |"
            )
        lines.extend(["", "### Provider Queries"])
        for index, query in enumerate(result["provider_queries"], start=1):
            lines.append(f"{index}. {query}")
        lines.extend(["", "### Query Results"])
        for query_result in result["query_results"]:
            suffix = f" / {query_result['location']}" if query_result["location"] else ""
            error = f" - {query_result['error']}" if query_result["error"] else ""
            lines.append(
                f"- `{query_result['query']}`{suffix}: {query_result['returned_count']} returned{error}"
            )
        lines.extend(["", "### Ranking Signals", fmt(result["ranking_signals"][:16]), "", "### Top Candidates", ""])
        lines.append("| # | Source | Title | Domain | Detail | Signals | Link |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for index, candidate in enumerate(result["top_candidates"][:12], start=1):
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(index),
                        md(candidate["source_provider"] or "unknown"),
                        md(candidate["title"] or "Untitled"),
                        md(candidate["domain"] or "unknown"),
                        md(candidate["detail_status"] or "unknown"),
                        md(fmt(candidate["matched_signals"])),
                        link(candidate["source_url"]),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def select_cases(case_ids: list[str]) -> list[MultidomainFlowCase]:
    if not case_ids:
        return list(MULTIDOMAIN_FLOW_CASES)
    wanted = set(case_ids)
    selected = [case for case in MULTIDOMAIN_FLOW_CASES if case.case_id in wanted]
    missing = sorted(wanted - {case.case_id for case in selected})
    if missing:
        raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
    return selected


def select_provider_queries(preview: dict[str, Any], limit: int) -> list[str]:
    queries = preview.get("provider_queries") or preview.get("recall_queries") or []
    result: list[str] = []
    seen: set[str] = set()
    for query in queries:
        item = str(query).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max(1, limit):
            break
    return result


def domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    return host.removeprefix("www.") if host else None


def fmt(values: list[Any]) -> str:
    if not values:
        return "None"
    return ", ".join(str(value) for value in values)


def fmt_counts(values: dict[str, int]) -> str:
    if not values:
        return "None"
    return ", ".join(f"{key} ({value})" for key, value in sorted(values.items()))


def md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def link(url: str | None) -> str:
    if not url:
        return "None"
    return f"[open]({url})"


if __name__ == "__main__":
    raise SystemExit(main())
