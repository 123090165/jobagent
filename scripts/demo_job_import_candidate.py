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

from app.schemas.job_import_candidate import JobImportCandidate
from app.services.errors import JobAgentError
from app.services.job_import_candidate_service import (
    create_candidate_from_brief_run,
    get_candidate,
    update_candidate,
)

DEFAULT_OUTPUT_DIR = "demo_runs/job_import_candidate"
DEFAULT_PUBLISH_DOCS_DIR = "docs/demo_runs"
JD_TEXT_PREVIEW_MAX_CHARS = 500
SCRIPT_VERSION = "v1"


class JobImportCandidateDemoError(ValueError):
    """User-facing runtime error for the job import candidate demo script."""


@dataclass
class JobImportCandidateRunResult:
    summary: dict[str, Any]
    output_dir: Path
    publish_dir: Path | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a JobImportCandidate from a saved brief_run recommendation.",
    )
    parser.add_argument("--run-id", required=True, help="Saved brief_run id.")
    parser.add_argument("--rank", type=int, default=1, help="Recommended rank to import. Default: 1")
    parser.add_argument(
        "--status",
        default="draft",
        help="Optional status update after import. Default: draft",
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
        help="Write sanitized outputs to docs/demo_runs/job_import_candidate_<timestamp>/",
    )
    return parser


def run_demo(
    args: argparse.Namespace,
    *,
    timestamp: str | None = None,
) -> JobImportCandidateRunResult:
    try:
        candidate = create_candidate_from_brief_run(args.run_id, rank=args.rank)
        desired_status = (args.status or "draft").strip() or "draft"
        if desired_status != candidate.status:
            candidate = update_candidate(candidate.candidate_id, status=desired_status)
        raw_candidate = get_candidate(candidate.candidate_id, include_full_jd=True)
        sanitized_candidate = get_candidate(candidate.candidate_id, include_full_jd=False)
    except JobAgentError as exc:
        raise JobImportCandidateDemoError(str(exc)) from exc

    if raw_candidate is None or sanitized_candidate is None:
        raise JobImportCandidateDemoError("Job import candidate could not be reloaded after creation.")

    stamp = timestamp or build_timestamp()
    output_dir = create_timestamped_dir(Path(args.output_dir), stamp)
    publish_dir = (
        create_timestamped_dir(Path(args.publish_docs_dir), f"job_import_candidate_{stamp}")
        if args.publish_sanitized
        else None
    )

    summary = build_summary(raw_candidate, run_id=args.run_id, rank=args.rank)
    write_json(output_dir / "candidate.json", raw_candidate.model_dump(mode="json"))
    write_text(output_dir / "README.md", build_output_readme(summary, output_dir))

    if publish_dir:
        write_json(publish_dir / "candidate_preview.json", build_sanitized_candidate_preview(sanitized_candidate))
        write_text(publish_dir / "README.md", build_publish_readme(summary, publish_dir))

    return JobImportCandidateRunResult(summary=summary, output_dir=output_dir, publish_dir=publish_dir)


def build_summary(candidate: JobImportCandidate, *, run_id: str, rank: int) -> dict[str, Any]:
    return {
        "script_version": SCRIPT_VERSION,
        "run_id": run_id,
        "rank": rank,
        "candidate_id": candidate.candidate_id,
        "status": candidate.status,
        "title": candidate.title,
        "company": candidate.company,
        "location": candidate.location,
        "quality_label": candidate.quality_label,
        "fit_score": candidate.fit_score,
    }


def build_sanitized_candidate_preview(candidate: JobImportCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "source": candidate.source,
        "source_run_id": candidate.source_run_id,
        "source_item_id": candidate.source_item_id,
        "title": candidate.title,
        "company": candidate.company,
        "location": candidate.location,
        "source_url": candidate.source_url,
        "quality_label": candidate.quality_label,
        "quality_score": candidate.quality_score,
        "fit_score": candidate.fit_score,
        "advice": candidate.advice,
        "status": candidate.status,
        "user_notes": candidate.user_notes,
        "jd_text_preview": (candidate.jd_text_preview or "")[:JD_TEXT_PREVIEW_MAX_CHARS],
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def build_output_readme(summary: dict[str, Any], output_dir: Path) -> str:
    return "\n".join(
        [
            "# Job Import Candidate Run",
            "",
            f"- Script Version: {summary['script_version']}",
            f"- Run ID: {summary['run_id']}",
            f"- Rank: {summary['rank']}",
            f"- Candidate ID: {summary['candidate_id']}",
            f"- Status: {summary['status']}",
            f"- Raw Output Directory: {output_dir}",
            "",
            "## Notes",
            "",
            "- This output may include full jd_text in the raw local file.",
            "- The docs/demo_runs publish path never stores full jd_text or resume_text.",
        ]
    ).strip() + "\n"


def build_publish_readme(summary: dict[str, Any], publish_dir: Path) -> str:
    return "\n".join(
        [
            "# Job Import Candidate Demo",
            "",
            f"- Script Version: {summary['script_version']}",
            f"- Run ID: {summary['run_id']}",
            f"- Rank: {summary['rank']}",
            f"- Candidate ID: {summary['candidate_id']}",
            f"- Status: {summary['status']}",
            f"- Publish Directory: {publish_dir}",
            "",
            "## Safety Boundary",
            "",
            "- No full resume_text is stored in docs/demo_runs.",
            "- No full jd_text is stored in docs/demo_runs.",
            f"- jd_text_preview is capped at {JD_TEXT_PREVIEW_MAX_CHARS} characters.",
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
    except JobImportCandidateDemoError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        "Job import candidate finished: "
        f"candidate_id={result.summary['candidate_id']}, "
        f"status={result.summary['status']}, "
        f"title={result.summary['title']}"
    )
    print(f"Raw output: {result.output_dir}")
    if result.publish_dir:
        print(f"Sanitized publish output: {result.publish_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
