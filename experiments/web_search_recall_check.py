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

from app.config.env_loader import load_local_env
from app.main import app
from app.services.job_search_providers.base import JobSearchProvider, RawJobCandidate
from app.services.job_search_providers.serper_web_provider import (
    SerperWebSearchProvider,
    configured_serper_search_sites,
)
from tests.fixtures.resumes.multidomain_flow_cases import (
    MULTIDOMAIN_FLOW_CASES,
    MultidomainFlowCase,
)


def main() -> int:
    args = parse_args()
    load_local_env(args.env_file)
    if args.search_site:
        os.environ["JOBAGENT_WEB_SEARCH_SITES"] = ",".join(args.search_site)

    provider = SerperWebSearchProvider()
    if not provider.configured:
        print(
            "Serper API key is missing. Set SERPER_API_KEY or JOBAGENT_SERPER_API_KEY "
            f"in {args.env_file}.",
            file=sys.stderr,
        )
        return 2

    cases = _select_cases(args.case_id)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with tempfile.TemporaryDirectory(prefix="jobagent_web_recall_", ignore_cleanup_errors=True) as temp_dir:
        os.environ["JOBAGENT_DB_PATH"] = str(Path(temp_dir) / "web_search_recall.sqlite3")
        client = TestClient(app)
        try:
            results = [
                run_case(
                    client=client,
                    case=case,
                    provider=provider,
                    queries_per_case=args.queries_per_case,
                    limit_per_query=args.limit_per_query,
                    include_location=not args.no_location,
                )
                for case in cases
            ]
        finally:
            client.close()

    json_path = output_dir / f"{timestamp}_web_search_recall_check.json"
    markdown_path = output_dir / f"{timestamp}_web_search_recall_check.md"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider.provider_name,
        "search_sites": configured_serper_search_sites(),
        "queries_per_case": args.queries_per_case,
        "limit_per_query": args.limit_per_query,
        "include_location": not args.no_location,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {markdown_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live Serper web-search recall check.")
    parser.add_argument(
        "--env-file",
        default=".env.deepseek.local",
        help="Local env file containing SERPER_API_KEY or JOBAGENT_SERPER_API_KEY.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Limit to one or more multidomain fixture case ids. Defaults to all cases.",
    )
    parser.add_argument(
        "--queries-per-case",
        type=int,
        default=2,
        help="Maximum recall queries to run per resume case.",
    )
    parser.add_argument(
        "--limit-per-query",
        type=int,
        default=10,
        help="Maximum Serper results per query.",
    )
    parser.add_argument(
        "--search-site",
        action="append",
        default=[],
        help="Optional site filter. Can be repeated. Overrides JOBAGENT_WEB_SEARCH_SITES for this run.",
    )
    parser.add_argument(
        "--no-location",
        action="store_true",
        help="Do not append the first preferred profile location to web-search queries.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "experiments" / "output"),
        help="Directory for JSON and Markdown reports.",
    )
    return parser.parse_args()


def run_case(
    *,
    client: TestClient,
    case: MultidomainFlowCase,
    provider: JobSearchProvider,
    queries_per_case: int,
    limit_per_query: int,
    include_location: bool,
) -> dict[str, Any]:
    preview_bundle = build_preview_bundle(client, case)
    confirmed = preview_bundle["confirmed"]
    preview = preview_bundle["preview"]
    recall_queries = _select_recall_queries(preview, queries_per_case)
    location = (preview["locations"] or confirmed["preferred_locations"] or [None])[0] if include_location else None
    query_runs = [
        _run_provider_query(provider, query=query, location=location, limit=limit_per_query)
        for query in recall_queries
    ]
    flattened = [item for result in query_runs for item in result["candidates"]]
    deduped = dedupe_candidates(flattened)
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
        "recall_queries": recall_queries,
        "ranking_signals": ranking_signals,
        "provider_search_urls": preview["provider_search_urls"],
        "query_results": [
            {
                "query": result["query"],
                "location": result["location"],
                "returned_count": result["returned_count"],
            }
            for result in query_runs
        ],
        "raw_candidate_count": len(flattened),
        "deduped_candidate_count": len(deduped),
        "duplicate_count": max(0, len(flattened) - len(deduped)),
        "source_domains": dict(Counter(item["domain"] for item in annotated if item["domain"])),
        "top_candidates": annotated[:20],
    }


def build_preview_bundle(client: TestClient, case: MultidomainFlowCase) -> dict[str, Any]:
    resume_text = case.path.read_text(encoding="utf-8")
    session = client.post("/api/v1/profile-sessions").json()
    session_id = session["session_id"]
    client.post(f"/api/v1/profile-sessions/{session_id}/resume-text", json={"text": resume_text})
    client.post(f"/api/v1/profile-sessions/{session_id}/parse-resume", params={"use_llm": False})
    draft = client.post(f"/api/v1/profile-sessions/{session_id}/profile-draft").json()["profile_draft"]
    confirmed = client.post(f"/api/v1/profile-drafts/{draft['profile_draft_id']}/confirm").json()[
        "confirmed_profile"
    ]
    preview = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "live_search",
            "search_provider": "serper_web",
            "use_llm": False,
            "max_results": 10,
        },
    ).json()
    return {"confirmed": confirmed, "preview": preview}


def _run_provider_query(
    provider: JobSearchProvider,
    *,
    query: str,
    location: str | None,
    limit: int,
) -> dict[str, Any]:
    candidates = provider.search_jobs(query=query, location=location, limit=limit)
    return {
        "query": query,
        "location": location,
        "returned_count": len(candidates),
        "candidates": candidates,
    }


def dedupe_candidates(candidates: list[RawJobCandidate]) -> list[RawJobCandidate]:
    result: list[RawJobCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


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
        "domain": _domain(candidate.source_url),
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
        "# Web Search Recall Check",
        "",
        f"Generated: {payload['generated_at']}",
        f"Provider: `{payload['provider']}`",
        f"Search sites: {_fmt(payload['search_sites'])}",
        f"Queries per case: {payload['queries_per_case']}",
        f"Limit per query: {payload['limit_per_query']}",
        f"Location appended: {payload['include_location']}",
        "",
        "This report calls the web-search provider for broad recall only. It does not call DeepSeek, does not run final LLM ranking, and does not fetch protected detail pages.",
        "",
    ]
    for result in payload["results"]:
        lines.extend(
            [
                f"## {result['case_id']}",
                "",
                f"Source file: `{result['source_file']}`",
                f"- target_roles: {_fmt(result['target_roles'])}",
                f"- target_directions: {_fmt(result['target_directions'])}",
                f"- preferred_locations: {_fmt(result['preferred_locations'])}",
                f"- raw candidates: {result['raw_candidate_count']}",
                f"- deduped candidates: {result['deduped_candidate_count']}",
                f"- duplicates: {result['duplicate_count']}",
                f"- source domains: {_fmt_domain_counts(result['source_domains'])}",
                "",
                "### Recall Queries",
            ]
        )
        for index, query in enumerate(result["recall_queries"], start=1):
            lines.append(f"{index}. {query}")
        lines.extend(["", "### Ranking Signals"])
        lines.append(_fmt(result["ranking_signals"][:16]))
        lines.extend(["", "### Query Results"])
        for query_result in result["query_results"]:
            lines.append(
                f"- `{query_result['query']}`"
                f"{f' / {query_result['location']}' if query_result['location'] else ''}: "
                f"{query_result['returned_count']} returned"
            )
        lines.extend(["", "### Top Candidates", ""])
        lines.append("| # | Title | Domain | Signals | Link |")
        lines.append("| --- | --- | --- | --- | --- |")
        for index, candidate in enumerate(result["top_candidates"][:12], start=1):
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(index),
                        _md(candidate["title"] or "Untitled"),
                        _md(candidate["domain"] or "unknown"),
                        _md(_fmt(candidate["matched_signals"])),
                        _link(candidate["source_url"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def _select_cases(case_ids: list[str]) -> list[MultidomainFlowCase]:
    if not case_ids:
        return list(MULTIDOMAIN_FLOW_CASES)
    wanted = set(case_ids)
    selected = [case for case in MULTIDOMAIN_FLOW_CASES if case.case_id in wanted]
    missing = sorted(wanted - {case.case_id for case in selected})
    if missing:
        raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
    return selected


def _select_recall_queries(preview: dict[str, Any], limit: int) -> list[str]:
    queries = preview.get("recall_queries") or preview.get("provider_queries") or []
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


def _candidate_key(candidate: RawJobCandidate) -> str:
    if candidate.source_url:
        return candidate.source_url.strip().lower().rstrip("/")
    return f"{candidate.title}:{candidate.company}:{candidate.location}".lower()


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    return host.removeprefix("www.") if host else None


def _fmt(values: list[Any]) -> str:
    if not values:
        return "None"
    return ", ".join(str(value) for value in values)


def _fmt_domain_counts(values: dict[str, int]) -> str:
    if not values:
        return "None"
    return ", ".join(f"{key} ({value})" for key, value in sorted(values.items()))


def _md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _link(url: str | None) -> str:
    if not url:
        return "None"
    return f"[open]({url})"


if __name__ == "__main__":
    raise SystemExit(main())
