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
from app.services.batch_brief_service import build_brief_from_search
from app.services.brief_run_storage_service import save_brief_run
from app.services.errors import JobAgentError
from app.services.public_job_storage_service import list_public_job_posts
from app.services.resume_file_service import ResumeFileParseError, extract_text_from_resume_file

DEFAULT_QUERY = "AI PyTorch 生理信号 深圳"
DEFAULT_LIMIT = 5
MAX_BRIEF_LIMIT = 10
DEFAULT_OUTPUT_DIR = "demo_runs/real_local_job_brief"
DEFAULT_PUBLISH_DOCS_DIR = "docs/demo_runs"
JD_TEXT_PREVIEW_MAX_CHARS = 500
SCRIPT_VERSION = "v1"


class RealLocalJobBriefDemoError(ValueError):
    """User-facing runtime error for the local job brief demo script."""


@dataclass
class RealLocalJobBriefRunResult:
    summary: dict[str, Any]
    output_dir: Path
    publish_dir: Path | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a real local_db Job Brief demo from collected public jobs.",
    )
    parser.add_argument(
        "--resume-file",
        required=True,
        help="Path to a local .txt or .md resume file.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f'Search query for local_db. Default: "{DEFAULT_QUERY}"',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of local jobs to brief. Default: {DEFAULT_LIMIT}",
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
        help="Write sanitized outputs to docs/demo_runs/real_local_job_brief_<timestamp>/",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Save the generated brief as a brief_run and include the run_id in outputs.",
    )
    return parser


def run_demo(
    args: argparse.Namespace,
    *,
    timestamp: str | None = None,
) -> RealLocalJobBriefRunResult:
    resume_text = read_resume_file(args.resume_file)
    query = (args.query or "").strip() or DEFAULT_QUERY
    limit = normalize_limit(args.limit)

    if not list_public_job_posts(limit=1):
        raise RealLocalJobBriefDemoError(
            "No public jobs found. Run collect_cuhksz_jobs.py first."
        )

    try:
        report = build_brief_from_search(
            resume_text=resume_text,
            query=query,
            provider="local_db",
            limit=limit,
            use_llm_jd=False,
        )
    except JobAgentError as exc:
        if exc.error_code == "brief_jobs_empty":
            raise RealLocalJobBriefDemoError(
                "No local_db jobs matched the query. Adjust the query or collect more public jobs first."
            ) from exc
        raise RealLocalJobBriefDemoError(str(exc)) from exc

    stamp = timestamp or build_timestamp()
    output_dir = create_timestamped_dir(Path(args.output_dir), stamp)
    publish_dir = (
        create_timestamped_dir(Path(args.publish_docs_dir), f"real_local_job_brief_{stamp}")
        if args.publish_sanitized
        else None
    )
    run_id = save_brief_run(report, resume_text) if args.save_run else None

    summary = build_brief_summary(
        report,
        resume_file=args.resume_file,
        query=query,
        limit=limit,
        run_id=run_id,
    )
    recommended_jobs = [build_recommended_job_record(item) for item in report.recommended_jobs]

    write_json(output_dir / "brief_summary.json", summary)
    write_json(output_dir / "recommended_jobs.json", recommended_jobs)
    write_text(output_dir / "README.md", build_output_readme(summary, output_dir))

    if publish_dir:
        preview_jobs = [build_recommended_job_preview(item) for item in report.recommended_jobs]
        write_json(publish_dir / "brief_summary.json", build_sanitized_summary(summary))
        write_json(publish_dir / "recommended_jobs_preview.json", preview_jobs)
        write_text(publish_dir / "README.md", build_publish_readme(summary, publish_dir))

    return RealLocalJobBriefRunResult(
        summary=summary,
        output_dir=output_dir,
        publish_dir=publish_dir,
    )


def read_resume_file(resume_file: str | Path) -> str:
    path = Path(resume_file)
    if not path.exists():
        raise RealLocalJobBriefDemoError(f"Resume file does not exist: {path}")

    try:
        content = path.read_bytes()
    except OSError as exc:
        raise RealLocalJobBriefDemoError(f"Failed to read resume file: {path}") from exc

    try:
        return extract_text_from_resume_file(path.name, content)
    except ResumeFileParseError as exc:
        raise RealLocalJobBriefDemoError(str(exc)) from exc


def normalize_limit(limit: int) -> int:
    try:
        normalized = int(limit)
    except (TypeError, ValueError) as exc:
        raise RealLocalJobBriefDemoError("limit must be an integer between 1 and 10") from exc

    if normalized < 1 or normalized > MAX_BRIEF_LIMIT:
        raise RealLocalJobBriefDemoError("limit must be between 1 and 10")
    return normalized


def build_brief_summary(
    report: JobBriefReport,
    *,
    resume_file: str | Path,
    query: str,
    limit: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "script_version": SCRIPT_VERSION,
        "run_id": run_id,
        "provider": report.provider,
        "query": query,
        "requested_limit": limit,
        "resume_file": str(Path(resume_file).as_posix()),
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
    return {
        "script_version": summary["script_version"],
        "provider": summary["provider"],
        "query": summary["query"],
        "requested_limit": summary["requested_limit"],
        "resume_file": summary["resume_file"],
        "total_jobs": summary["total_jobs"],
        "recommended_job_count": summary["recommended_job_count"],
        "top_skills": summary["top_skills"],
        "market_summary": summary["market_summary"],
        "application_strategy": summary["application_strategy"],
        "scoring_quality_summary": summary["scoring_quality_summary"],
    }


def build_output_readme(summary: dict[str, Any], output_dir: Path) -> str:
    return "\n".join(
        [
            "# Real Local Job Brief Run",
            "",
            f"- Script Version: {summary['script_version']}",
            f"- Run ID: {summary['run_id'] or 'N/A'}",
            f"- Provider: {summary['provider']}",
            f"- Query: {summary['query']}",
            f"- Requested Limit: {summary['requested_limit']}",
            f"- Resume File: {summary['resume_file']}",
            f"- Total Jobs: {summary['total_jobs']}",
            f"- Recommended Job Count: {summary['recommended_job_count']}",
            f"- Raw Output Directory: {output_dir}",
            "",
            "## Notes",
            "",
            "- This raw local output may include full jd_text for debugging and validation.",
            "- The docs/demo_runs sanitized publish path never stores full resume_text or full jd_text.",
        ]
    ).strip() + "\n"


def build_publish_readme(summary: dict[str, Any], publish_dir: Path) -> str:
    return "\n".join(
        [
            "# Real Local Job Brief Demo",
            "",
            f"- Script Version: {summary['script_version']}",
            f"- Run ID: {summary['run_id'] or 'N/A'}",
            f"- Provider: {summary['provider']}",
            f"- Query: {summary['query']}",
            f"- Requested Limit: {summary['requested_limit']}",
            f"- Resume File: {summary['resume_file']}",
            f"- Total Jobs: {summary['total_jobs']}",
            f"- Recommended Job Count: {summary['recommended_job_count']}",
            f"- Publish Directory: {publish_dir}",
            "",
            "## Safety Boundary",
            "",
            "- No full resume_text is stored in docs/demo_runs.",
            "- No full jd_text is stored in docs/demo_runs.",
            f"- jd_text_preview is capped at {JD_TEXT_PREVIEW_MAX_CHARS} characters.",
            "- This demo only reuses previously collected local_db jobs.",
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
    except RealLocalJobBriefDemoError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        "Real local Job Brief finished: "
        f"run_id={result.summary['run_id'] or 'N/A'}, "
        f"provider={result.summary['provider']}, "
        f"query={result.summary['query']}, "
        f"recommended_jobs={result.summary['recommended_job_count']}"
    )
    print(f"Raw output: {result.output_dir}")
    if result.publish_dir:
        print(f"Sanitized publish output: {result.publish_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
