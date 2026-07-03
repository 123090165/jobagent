from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.env_loader import load_local_env
from app.services.job_search_providers import (
    AVAILABLE_JOB_SEARCH_SOURCES,
    encode_selected_sources,
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
    get_job_search_provider_status,
    normalize_job_search_provider_name,
    resolve_job_search_provider,
)
from app.services.job_search_recall_metrics import build_source_recall_stats


def main() -> int:
    args = parse_args()
    load_local_env(args.env_file)
    provider_name = resolve_provider_name(args.provider, args.source)
    query = resolve_smoke_query(args.query, args.url)
    provider = resolve_job_search_provider(provider_name)
    result = run_smoke_check(
        provider=provider,
        provider_name=provider_name,
        query=query,
        location=args.location,
        limit=args.limit,
        min_candidates=args.min_candidates,
        require_detail=args.require_detail,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_url": args.url,
        "provider_status": get_job_search_provider_status(provider_name),
        "selected_sources": args.source if normalize_job_search_provider_name(args.provider) == "multi_source" else [],
        **result,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_provider = provider_name.replace(":", "_").replace(",", "_")
    json_path = output_dir / f"{timestamp}_{safe_provider}_provider_live_smoke.json"
    markdown_path = output_dir / f"{timestamp}_{safe_provider}_provider_live_smoke.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {markdown_path}")
    return 0 if payload["passed"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a reusable live smoke check through the unified JobSearchProvider interface."
    )
    parser.add_argument(
        "--provider",
        default="cuhksz_career",
        choices=["cuhksz_career", "linkedin", "remoteok", "serper_web", "multi_source"],
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=AVAILABLE_JOB_SEARCH_SOURCES,
        default=[],
        help="Selected source for multi_source. Can be repeated. Defaults to all frontend sources.",
    )
    parser.add_argument("--query", default=None, help="Provider query. If omitted, --url must include q/title/query.")
    parser.add_argument("--url", default=None, help="Optional search URL to derive the query from.")
    parser.add_argument("--location", default=None)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--min-candidates", type=int, default=1)
    parser.add_argument(
        "--require-detail",
        action="store_true",
        help="Fail if no returned candidate has raw_description/detail content.",
    )
    parser.add_argument(
        "--env-file",
        default=".env.deepseek.local",
        help="Local env file for API-key backed providers. CUHKSZ does not require one.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "experiments" / "output"),
        help="Directory for JSON and Markdown reports.",
    )
    return parser.parse_args()


def resolve_provider_name(provider: str, sources: list[str]) -> str:
    normalized = normalize_job_search_provider_name(provider)
    if normalized == "multi_source":
        return encode_selected_sources(sources or list(AVAILABLE_JOB_SEARCH_SOURCES))
    return normalized


def resolve_smoke_query(query: str | None, url: str | None) -> str:
    if query and query.strip():
        return query.strip()
    if not url:
        raise ValueError("Either --query or --url is required.")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("title", "q", "query", "keyword", "keywords"):
        values = params.get(key)
        if values and values[0].strip():
            return values[0].strip()
    raise ValueError("Could not derive a provider query from --url.")


def run_smoke_check(
    *,
    provider: JobSearchProvider,
    provider_name: str,
    query: str,
    location: str | None,
    limit: int,
    min_candidates: int,
    require_detail: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        candidates = provider.search_jobs(query=query, location=location, limit=limit)
    except JobSearchProviderError as exc:
        candidates = []
        errors.append(f"{type(exc).__name__}: {exc}")

    source_stats = build_source_recall_stats(candidates, candidates)
    candidate_items = [candidate_to_dict(candidate) for candidate in candidates]
    candidates_with_url = [candidate for candidate in candidates if candidate.source_url]
    candidates_with_detail = [
        candidate for candidate in candidates if (candidate.raw_description or "").strip()
    ]
    if len(candidates) < min_candidates:
        errors.append(f"Expected at least {min_candidates} candidate(s), got {len(candidates)}.")
    if not candidates_with_url:
        errors.append("No candidate included a source URL.")
    if require_detail and not candidates_with_detail:
        errors.append("No candidate included detail/raw_description content.")

    return {
        "provider": provider_name,
        "provider_kind": getattr(provider, "provider_kind", "unknown"),
        "query": query,
        "location": location,
        "limit": limit,
        "min_candidates": min_candidates,
        "require_detail": require_detail,
        "passed": not errors,
        "errors": errors,
        "candidate_count": len(candidates),
        "candidate_with_url_count": len(candidates_with_url),
        "candidate_with_detail_count": len(candidates_with_detail),
        "source_stats": [item.to_dict() for item in source_stats],
        "candidates": candidate_items,
    }


def candidate_to_dict(candidate: RawJobCandidate) -> dict[str, Any]:
    return {
        "title": candidate.title,
        "company": candidate.company,
        "location": candidate.location,
        "source_provider": candidate.source_provider,
        "source_url": candidate.source_url,
        "snippet": candidate.snippet,
        "raw_description_length": len(candidate.raw_description or ""),
        "discovery_query": candidate.discovery_query,
        "discovery_rank": candidate.discovery_rank,
        "detail_status": candidate.detail_status,
        "provider_warnings": candidate.provider_warnings,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Provider Live Smoke Check",
        "",
        f"Generated: {payload['generated_at']}",
        f"Provider: `{payload['provider']}`",
        f"Selected sources: {', '.join(payload.get('selected_sources') or []) or 'None'}",
        f"Query: `{payload['query']}`",
        f"Location: {payload['location'] or 'None'}",
        f"Input URL: {payload['input_url'] or 'None'}",
        f"Passed: {payload['passed']}",
        f"Candidates: {payload['candidate_count']}",
        f"With source URL: {payload['candidate_with_url_count']}",
        f"With detail: {payload['candidate_with_detail_count']}",
        "",
    ]
    if payload["errors"]:
        lines.extend(["## Errors", ""])
        for error in payload["errors"]:
            lines.append(f"- {error}")
        lines.append("")
    lines.extend(
        [
            "## Source Stats",
            "",
            "| Source | Raw | Deduped | Missing URL | Missing Detail | Detail Coverage | Warnings |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for stat in payload["source_stats"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md(stat["source_provider"]),
                    str(stat["raw_candidate_count"]),
                    str(stat["deduped_candidate_count"]),
                    str(stat["missing_url_count"]),
                    str(stat["missing_detail_count"]),
                    str(stat["detail_coverage_rate"]),
                    str(stat["warning_count"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Candidates", ""])
    lines.append("| # | Title | Company | Location | Detail | Raw Length | Link |")
    lines.append("| --- | --- | --- | --- | --- | ---: | --- |")
    for index, candidate in enumerate(payload["candidates"], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    md(candidate["title"] or "Untitled"),
                    md(candidate["company"] or "Unknown"),
                    md(candidate["location"] or "Unspecified"),
                    md(candidate["detail_status"] or "unknown"),
                    str(candidate["raw_description_length"]),
                    link(candidate["source_url"]),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def link(url: str | None) -> str:
    if not url:
        return "None"
    return f"[open]({url})"


if __name__ == "__main__":
    raise SystemExit(main())
