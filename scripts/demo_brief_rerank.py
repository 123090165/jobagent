from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.services.brief_rerank_service import rerank_brief_run
from app.services.errors import JobAgentError

DEFAULT_OUTPUT_DIR = "demo_runs/brief_rerank"
DEFAULT_PUBLISH_DOCS_DIR = "docs/demo_runs"
DEFAULT_LIMIT = 5
JD_TEXT_PREVIEW_MAX_CHARS = 500
SCRIPT_VERSION = "v1"


class BriefRerankDemoError(ValueError):
    """User-facing runtime error for the brief rerank demo script."""


@dataclass
class BriefRerankRunResult:
    summary: dict[str, Any]
    output_dir: Path
    publish_dir: Path | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rerank a saved brief_run without re-searching or recollecting jobs.",
    )
    parser.add_argument("--run-id", required=True, help="Saved brief_run id.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max reranked jobs to return. Default: {DEFAULT_LIMIT}",
    )
    parser.add_argument(
        "--min-fit-score",
        type=float,
        default=None,
        help="Minimum original fit score to keep in rerank.",
    )
    parser.add_argument(
        "--location-keywords",
        nargs="*",
        default=[],
        help="Optional location keywords for rerank boosting.",
    )
    parser.add_argument(
        "--include-keywords",
        nargs="*",
        default=[],
        help="Optional keywords that boost matching items.",
    )
    parser.add_argument(
        "--exclude-keywords",
        nargs="*",
        default=[],
        help="Optional keywords that filter out matching items.",
    )
    parser.add_argument(
        "--require-full-jd",
        action="store_true",
        help="Keep only full_jd items.",
    )
    parser.add_argument(
        "--exclude-external-link-only",
        action="store_true",
        help="Drop external_link_only items.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Raw local output base directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--publish-docs-dir",
        default=DEFAULT_PUBLISH_DOCS_DIR,
        help=f"Sanitized publish base directory. Default: {DEFAULT_PUBLISH_DOCS_DIR}",
    )
    parser.add_argument(
        "--publish-sanitized",
        action="store_true",
        help="Write sanitized outputs to docs/demo_runs/brief_rerank_<timestamp>/",
    )
    return parser


def run_demo(
    args: argparse.Namespace,
    *,
    timestamp: str | None = None,
) -> BriefRerankRunResult:
    try:
        report = rerank_brief_run(
            run_id=args.run_id,
            require_full_jd=bool(args.require_full_jd),
            exclude_external_link_only=bool(args.exclude_external_link_only),
            location_keywords=list(args.location_keywords or []),
            include_keywords=list(args.include_keywords or []),
            exclude_keywords=list(args.exclude_keywords or []),
            min_fit_score=args.min_fit_score,
            limit=args.limit,
        )
    except JobAgentError as exc:
        raise BriefRerankDemoError(str(exc)) from exc

    stamp = timestamp or build_timestamp()
    output_dir = create_timestamped_dir(Path(args.output_dir), stamp)
    publish_dir = (
        create_timestamped_dir(Path(args.publish_docs_dir), f"brief_rerank_{stamp}")
        if args.publish_sanitized
        else None
    )

    summary = build_brief_summary(report, args=args)
    recommended_jobs = [build_recommended_job_record(item) for item in report.recommended_jobs]

    write_json(output_dir / "brief_summary.json", summary)
    write_json(output_dir / "recommended_jobs.json", recommended_jobs)
    write_text(output_dir / "README.md", build_output_readme(summary, output_dir))

    if publish_dir:
        preview_jobs = [build_recommended_job_preview(item) for item in report.recommended_jobs]
        write_json(publish_dir / "brief_summary.json", build_sanitized_summary(summary))
        write_json(publish_dir / "recommended_jobs_preview.json", preview_jobs)
        write_text(publish_dir / "README.md", build_publish_readme(summary, publish_dir))

    return BriefRerankRunResult(
        summary=summary,
        output_dir=output_dir,
        publish_dir=publish_dir,
    )


def build_brief_summary(report: JobBriefReport, *, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "script_version": SCRIPT_VERSION,
        "run_id": args.run_id,
        "provider": report.provider,
        "query": report.query,
        "requested_limit": args.limit,
        "require_full_jd": bool(args.require_full_jd),
        "exclude_external_link_only": bool(args.exclude_external_link_only),
        "location_keywords": list(args.location_keywords or []),
        "include_keywords": list(args.include_keywords or []),
        "exclude_keywords": list(args.exclude_keywords or []),
        "min_fit_score": args.min_fit_score,
        "total_jobs": report.total_jobs,
        "recommended_job_count": len(report.recommended_jobs),
        "top_skills": report.top_skills,
        "market_summary": report.market_summary,
        "application_strategy": report.application_strategy,
        "scoring_quality_summary": report.scoring_quality_summary,
    }


def build_recommended_job_record(item: JobRecommendationItem) -> dict[str, Any]:
    job = item.job
    return {
        "rank": item.rank,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source,
        "source_url": job.url,
        "snippet": job.snippet,
        "jd_text": job.jd_text,
        "responsibilities": job.responsibilities,
        "requirements": job.requirements,
        "skills": job.skills,
        "quality_label": job.quality_label,
        "quality_warnings": job.warnings,
        "external_links": job.external_links,
        "is_full_jd": job.is_full_jd,
        "confidence": job.confidence,
        "fit_score": item.fit_score,
        "scoring_quality": item.scoring_quality,
        "advice": item.advice,
        "fit_reasons": item.fit_reasons,
        "risk_points": item.risk_points,
        "match_report": item.match_report.model_dump(mode="json"),
    }


def build_recommended_job_preview(item: JobRecommendationItem) -> dict[str, Any]:
    job = item.job
    jd_preview_source = (job.jd_text or job.snippet or "").strip()
    return {
        "rank": item.rank,
        "title": job.title,
        "company": job.company,
        "source_url": job.url,
        "fit_score": item.fit_score,
        "scoring_quality": item.scoring_quality,
        "quality_label": job.quality_label or item.scoring_quality,
        "is_full_jd": job.is_full_jd,
        "confidence": job.confidence,
        "advice": item.advice,
        "jd_text_preview": jd_preview_source[:JD_TEXT_PREVIEW_MAX_CHARS],
    }


def build_sanitized_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return dict(summary)


def build_output_readme(summary: dict[str, Any], output_dir: Path) -> str:
    return "\n".join(
        [
            "# Brief Rerank Run",
            "",
            f"- Script Version: {summary['script_version']}",
            f"- Run ID: {summary['run_id']}",
            f"- Provider: {summary['provider']}",
            f"- Query: {summary['query']}",
            f"- Requested Limit: {summary['requested_limit']}",
            f"- Recommended Job Count: {summary['recommended_job_count']}",
            f"- Raw Output Directory: {output_dir}",
            "",
            "## Notes",
            "",
            "- This rerank reuses only saved brief_run results.",
            "- No re-search, recollection, or full brief rebuild happens here.",
        ]
    ).strip() + "\n"


def build_publish_readme(summary: dict[str, Any], publish_dir: Path) -> str:
    return "\n".join(
        [
            "# Brief Rerank Demo",
            "",
            f"- Script Version: {summary['script_version']}",
            f"- Run ID: {summary['run_id']}",
            f"- Provider: {summary['provider']}",
            f"- Query: {summary['query']}",
            f"- Requested Limit: {summary['requested_limit']}",
            f"- Recommended Job Count: {summary['recommended_job_count']}",
            f"- Publish Directory: {publish_dir}",
            "",
            "## Safety Boundary",
            "",
            "- No full resume_text is stored in docs/demo_runs.",
            "- No full jd_text is stored in docs/demo_runs.",
            f"- jd_text_preview is capped at {JD_TEXT_PREVIEW_MAX_CHARS} characters.",
            "- This rerank only reuses a previously saved brief_run.",
        ]
    ).strip() + "\n"


def create_timestamped_dir(base_dir: Path, stamp: str) -> Path:
    candidate = base_dir / stamp
    suffix = 1
    while candidate.exists():
        candidate = base_dir / f"{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def build_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_demo(args)
    except BriefRerankDemoError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        "Brief rerank finished: "
        f"run_id={result.summary['run_id']}, "
        f"query={result.summary['query']}, "
        f"recommended_jobs={result.summary['recommended_job_count']}"
    )
    print(f"Raw output: {result.output_dir}")
    if result.publish_dir:
        print(f"Sanitized publish output: {result.publish_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
