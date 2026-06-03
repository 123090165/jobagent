from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.cuhksz_career import CUHKSZCollectSummary, CUHKSZJobDetail
from app.services.cuhksz_career_service import (
    build_cuhksz_job_detail,
    fetch_cuhksz_job_detail,
    fetch_public_html,
    parse_cuhksz_job_list,
)
from app.services.public_job_storage_service import save_public_job_post

DEFAULT_LIST_URL = "https://career.cuhk.edu.cn/job/search/d_category/102"
DEFAULT_OUTPUT_DIR = "demo_runs/cuhksz_collect"
DOCS_DEMO_RUNS_DIR = "docs/demo_runs"
DEFAULT_DETAIL_TIMEOUT_SECONDS = 15
DETAIL_REQUEST_SLEEP_SECONDS = 0.5
MAX_LIMIT = 50
SCRIPT_VERSION = "v1"


@dataclass
class CollectorRunResult:
    summary: CUHKSZCollectSummary
    output_dir: Path
    publish_dir: Path | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect public CUHKSZ career jobs into local SQLite.",
    )
    parser.add_argument(
        "--list-url",
        default=DEFAULT_LIST_URL,
        help=f"Public CUHKSZ list page URL. Default: {DEFAULT_LIST_URL}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=f"Number of jobs to collect from the current list page. Max: {MAX_LIMIT}",
    )
    parser.add_argument(
        "--detail-timeout-seconds",
        type=int,
        default=DEFAULT_DETAIL_TIMEOUT_SECONDS,
        help=f"Timeout for each detail request. Default: {DEFAULT_DETAIL_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write reports only; do not write to SQLite.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Raw local output base directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--publish-sanitized",
        action="store_true",
        help="Write sanitized docs/demo_runs/cuhksz_collect_<timestamp>/ artifacts.",
    )
    return parser


def run_collection(
    args: argparse.Namespace,
    *,
    timestamp: str | None = None,
) -> CollectorRunResult:
    stamp = timestamp or build_timestamp()
    output_dir = create_timestamped_dir(Path(args.output_dir), stamp)
    publish_dir = (
        create_timestamped_dir(Path(DOCS_DEMO_RUNS_DIR), f"cuhksz_collect_{stamp}")
        if args.publish_sanitized
        else None
    )
    limit = normalize_limit(args.limit)
    errors: list[dict[str, Any]] = []
    details: list[CUHKSZJobDetail] = []
    saved_count = 0
    skipped_count = 0
    detail_success_count = 0
    detail_failed_count = 0

    try:
        list_html = fetch_public_html(args.list_url, timeout_seconds=args.detail_timeout_seconds)
        list_items = parse_cuhksz_job_list(list_html, args.list_url)
    except Exception as exc:
        error = build_error("list_fetch_or_parse_failed", args.list_url, exc)
        errors.append(error)
        summary = CUHKSZCollectSummary(
            list_url=args.list_url,
            fetched_count=0,
            detail_success_count=0,
            detail_failed_count=0,
            saved_count=0,
            skipped_count=0,
            errors=[error["message"]],
        )
        write_reports(output_dir, summary, details, errors)
        if publish_dir:
            write_sanitized_reports(publish_dir, output_dir, summary, details)
        return CollectorRunResult(summary=summary, output_dir=output_dir, publish_dir=publish_dir)

    selected_items = list_items[:limit]
    for index, item in enumerate(selected_items):
        try:
            detail_html = fetch_cuhksz_job_detail(
                item.detail_url,
                timeout_seconds=args.detail_timeout_seconds,
            )
            detail = build_cuhksz_job_detail(item, detail_html)
            details.append(detail)
            detail_success_count += 1
            if args.dry_run:
                skipped_count += 1
            else:
                save_public_job_post(detail)
                saved_count += 1
        except Exception as exc:
            detail_failed_count += 1
            skipped_count += 1
            errors.append(build_error("detail_collect_failed", item.detail_url, exc, external_id=item.external_id))

        if index < len(selected_items) - 1:
            time.sleep(DETAIL_REQUEST_SLEEP_SECONDS)

    summary = CUHKSZCollectSummary(
        list_url=args.list_url,
        fetched_count=len(selected_items),
        detail_success_count=detail_success_count,
        detail_failed_count=detail_failed_count,
        saved_count=saved_count,
        skipped_count=skipped_count,
        errors=[error["message"] for error in errors],
    )
    write_reports(output_dir, summary, details, errors)
    if publish_dir:
        write_sanitized_reports(publish_dir, output_dir, summary, details)
    return CollectorRunResult(summary=summary, output_dir=output_dir, publish_dir=publish_dir)


def run_collect(args: argparse.Namespace) -> int:
    result = run_collection(args)
    summary = result.summary
    print(
        "CUHKSZ collect finished: "
        f"fetched={summary.fetched_count}, "
        f"details={summary.detail_success_count}, "
        f"failed={summary.detail_failed_count}, "
        f"saved={summary.saved_count}, "
        f"skipped={summary.skipped_count}"
    )
    print(f"Raw report: {result.output_dir}")
    if result.publish_dir:
        print(f"Sanitized report: {result.publish_dir}")
    return 0 if summary.detail_failed_count == 0 and not summary.errors else 1


def build_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


def create_timestamped_dir(base_dir: Path, stamp: str) -> Path:
    candidate = base_dir / stamp
    suffix = 1
    while candidate.exists():
        candidate = base_dir / f"{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def write_reports(
    output_dir: Path,
    summary: CUHKSZCollectSummary,
    details: list[CUHKSZJobDetail],
    errors: list[dict[str, Any]],
) -> None:
    write_json(output_dir / "collect_summary.json", summary.model_dump(mode="json"))
    write_json(output_dir / "collected_jobs.json", [detail_to_report_dict(detail) for detail in details])
    write_json(output_dir / "errors.json", errors)


def write_sanitized_reports(
    publish_dir: Path,
    raw_output_dir: Path,
    summary: CUHKSZCollectSummary,
    details: list[CUHKSZJobDetail],
) -> None:
    write_text(publish_dir / "README.md", build_publish_readme(summary, raw_output_dir))
    write_json(publish_dir / "collect_summary.json", summary.model_dump(mode="json"))
    write_json(
        publish_dir / "collected_jobs_preview.json",
        [detail_to_preview_dict(detail) for detail in details],
    )


def detail_to_report_dict(detail: CUHKSZJobDetail) -> dict[str, Any]:
    item = detail.list_item
    return {
        "external_id": item.external_id,
        "title": item.title,
        "company": item.company,
        "location": item.location,
        "job_type": item.job_type,
        "education": item.education,
        "published_at": item.published_at,
        "deadline": item.deadline,
        "source": item.source,
        "source_url": item.detail_url,
        "snippet": detail.snippet,
        "jd_text": detail.jd_text,
        "quality_label": detail.quality_label,
        "is_full_jd": detail.is_full_jd,
        "confidence": detail.confidence,
        "extraction_method": detail.extraction_method,
        "warnings": detail.warnings,
        "external_links": detail.external_links,
    }


def detail_to_preview_dict(detail: CUHKSZJobDetail) -> dict[str, Any]:
    item = detail.list_item
    return {
        "external_id": item.external_id,
        "title": item.title,
        "company": item.company,
        "source_url": item.detail_url,
        "quality_label": detail.quality_label,
        "is_full_jd": detail.is_full_jd,
        "confidence": detail.confidence,
        "warnings": detail.warnings,
        "jd_text_preview": detail.jd_text[:500],
    }


def build_publish_readme(summary: CUHKSZCollectSummary, raw_output_dir: Path) -> str:
    return "\n".join(
        [
            "# CUHKSZ Career Collector Run",
            "",
            f"- Script Version: {SCRIPT_VERSION}",
            f"- List URL: {summary.list_url}",
            f"- Fetched Count: {summary.fetched_count}",
            f"- Detail Success Count: {summary.detail_success_count}",
            f"- Detail Failed Count: {summary.detail_failed_count}",
            f"- Saved Count: {summary.saved_count}",
            f"- Skipped Count: {summary.skipped_count}",
            f"- Raw Output Directory: {raw_output_dir}",
            "",
            "## Safety Boundary",
            "",
            "- Public http/https pages only.",
            "- No login, cookies, captcha handling, JavaScript execution, Playwright, or Selenium.",
            "- This run only collects the current list page up to the configured limit.",
            "- Published previews do not include full jd_text.",
        ]
    ).strip() + "\n"


def build_error(
    kind: str,
    url: str,
    exc: Exception,
    *,
    external_id: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "external_id": external_id,
        "url": url,
        "message": str(exc),
        "error_type": type(exc).__name__,
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_collect(args)


if __name__ == "__main__":
    raise SystemExit(main())
