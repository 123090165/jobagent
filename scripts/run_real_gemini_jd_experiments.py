from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = "demo_runs"
DEFAULT_PUBLISH_DOCS_DIR = "docs/demo_runs"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RUNS = 5
SUBPROCESS_TIMEOUT_BUFFER_SECONDS = 15
SUMMARY_MARKDOWN_NAME = "REAL_GEMINI_JD_EXPERIMENT_SUMMARY.md"
SUMMARY_JSON_NAME = "real_gemini_jd_experiment_summary.json"
DEFAULT_QUERIES = [
    "腾讯 深圳 AI Agent 开发工程师 招聘",
    "Tencent Shenzhen LLM application engineer job posting",
    "ByteDance AI Agent engineer job posting",
]
GOOD_STATUS = "GOOD"
PARTIAL_STATUS = "PARTIAL"
FAILED_STATUS = "FAILED"
JOB_URL_HINTS = (
    "job",
    "jobs",
    "career",
    "careers",
    "position",
    "recruit",
    "apply",
    "campus",
    "opportunit",
)
JD_TEXT_HINTS = (
    "responsibil",
    "requirement",
    "qualification",
    "skill",
    "职责",
    "要求",
    "技能",
)


class RealGeminiExperimentsError(ValueError):
    """User-facing runtime error for the real Gemini JD experiments script."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run multiple real Gemini JD search experiments through the existing demo flow.",
    )
    parser.add_argument(
        "--resume-file",
        required=True,
        help="Path to a local .txt or .md resume file.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for raw local outputs. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--publish-docs-dir",
        default=DEFAULT_PUBLISH_DOCS_DIR,
        help=f"Directory for sanitized publishable outputs. Default: {DEFAULT_PUBLISH_DOCS_DIR}",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Repeatable search query. Can be provided multiple times.",
    )
    parser.add_argument(
        "--query-file",
        help="Optional UTF-8 text file with one query per line.",
    )
    parser.add_argument(
        "--api-base-url",
        default=None,
        help="Optional FastAPI base URL passed through to demo_gemini_search_flow.py.",
    )
    parser.add_argument(
        "--start-api",
        action="store_true",
        help="Pass --start-api through to demo_gemini_search_flow.py.",
    )
    parser.add_argument(
        "--try-import-url",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to pass --try-import-url to the demo flow. Default: enabled.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Pass --use-llm through to demo_gemini_search_flow.py.",
    )
    parser.add_argument(
        "--use-langgraph",
        action="store_true",
        help="Pass --use-langgraph through to demo_gemini_search_flow.py.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout passed to the demo flow. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=DEFAULT_MAX_RUNS,
        help=f"Maximum number of queries to run. Default: {DEFAULT_MAX_RUNS}",
    )
    return parser


def load_queries(
    raw_queries: list[str] | None,
    query_file: str | Path | None,
    *,
    max_runs: int = DEFAULT_MAX_RUNS,
) -> list[str]:
    if max_runs < 1:
        raise RealGeminiExperimentsError("max-runs must be at least 1")

    queries: list[str] = []
    if raw_queries:
        queries.extend(_normalize_queries(raw_queries))
    if query_file:
        queries.extend(load_queries_from_file(query_file))
    if not queries:
        queries = list(DEFAULT_QUERIES)

    if not queries:
        raise RealGeminiExperimentsError("No valid queries were provided")
    return queries[:max_runs]


def load_queries_from_file(query_file: str | Path) -> list[str]:
    path = Path(query_file)
    if not path.exists():
        raise RealGeminiExperimentsError(f"Query file does not exist: {path}")
    try:
        contents = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RealGeminiExperimentsError("Query file must be UTF-8 text") from exc
    return _normalize_queries(contents.splitlines())


def _normalize_queries(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def build_demo_command(args: argparse.Namespace, query: str, project_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(project_root / "scripts" / "demo_gemini_search_flow.py"),
        "--query",
        query,
        "--resume-file",
        str(args.resume_file),
        "--output-dir",
        str(args.output_dir),
        "--publish-docs-dir",
        str(args.publish_docs_dir),
        "--publish-sanitized",
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.api_base_url:
        command.extend(["--api-base-url", str(args.api_base_url)])
    if args.start_api:
        command.append("--start-api")
    if args.try_import_url:
        command.append("--try-import-url")
    if args.use_llm:
        command.append("--use-llm")
    if args.use_langgraph:
        command.append("--use-langgraph")
    return command


def get_subprocess_timeout(timeout_seconds: int) -> int:
    if timeout_seconds < 1:
        raise RealGeminiExperimentsError("timeout-seconds must be at least 1")
    return timeout_seconds + SUBPROCESS_TIMEOUT_BUFFER_SECONDS


def list_timestamp_dirs(base_dir: str | Path) -> list[Path]:
    path = Path(base_dir)
    if not path.exists():
        return []
    return sorted((child for child in path.iterdir() if child.is_dir()), key=lambda child: child.name)


def find_new_publish_dir(base_dir: str | Path, known_dir_names: set[str]) -> Path | None:
    candidates = [path for path in list_timestamp_dirs(base_dir) if path.name not in known_dir_names]
    if not candidates:
        return None
    return candidates[-1]


def parse_publish_readme(readme_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in readme_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        values[key.strip()] = value.strip()
    return values


def parse_markdown_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def clamp_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def looks_like_job_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = str(url).strip().lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    return any(hint in lowered for hint in JOB_URL_HINTS)


def preview_contains_jd_signals(preview: str | None) -> bool:
    if not preview:
        return False
    lowered = str(preview).strip().lower()
    return any(hint in lowered for hint in JD_TEXT_HINTS)


def build_run_notes(run: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if run.get("search_failed"):
        notes.append("Search step failed.")
    if run.get("analysis_succeeded") is not True:
        notes.append("Analyze step did not succeed.")
    if run.get("selected_url"):
        if looks_like_job_url(str(run.get("selected_url"))):
            notes.append("Selected URL looks like a direct job page.")
        else:
            notes.append("Selected URL may not look like a direct job page.")
    else:
        notes.append("No selected URL was returned.")
    if run.get("selected_is_full_jd") is True:
        notes.append("Gemini marked the result as a full JD.")
    else:
        notes.append("Gemini did not mark the result as a full JD.")

    confidence = clamp_confidence(run.get("selected_confidence"))
    if confidence >= 0.7:
        notes.append("Gemini confidence is at least 0.7.")
    else:
        notes.append("Gemini confidence is below 0.7.")

    if preview_contains_jd_signals(str(run.get("selected_jd_text_preview", ""))):
        notes.append("JD preview includes responsibility/requirement/skill signals.")
    else:
        notes.append("JD preview does not clearly show responsibility/requirement/skill signals.")

    if run.get("url_import_succeeded") is True:
        notes.append("URL import succeeded.")
    elif run.get("url_import_succeeded") is False:
        notes.append("URL import did not succeed.")

    if run.get("used_fallback_jd") is True:
        notes.append("Fallback JD draft was used.")

    for extra_note in run.get("extra_notes", []):
        if extra_note:
            notes.append(str(extra_note))
    return notes


def classify_run_result(run: dict[str, Any]) -> str:
    analysis_succeeded = run.get("analysis_succeeded") is True
    has_selected_item = bool(str(run.get("selected_title", "")).strip())
    has_selected_url = bool(str(run.get("selected_url", "")).strip())
    confidence = clamp_confidence(run.get("selected_confidence"))
    is_full_jd = run.get("selected_is_full_jd") is True

    if not has_selected_item or not analysis_succeeded:
        return FAILED_STATUS
    if has_selected_url and confidence >= 0.7 and is_full_jd:
        return GOOD_STATUS
    return PARTIAL_STATUS


def load_run_result(query: str, docs_run_dir: Path) -> dict[str, Any]:
    readme_text = load_text_file(docs_run_dir / "README.md")
    readme_values = parse_publish_readme(readme_text)
    search_summary = load_json_file(docs_run_dir / "search_summary.json")
    analysis_summary = load_json_file(docs_run_dir / "analysis_summary.json")
    run_metadata = load_json_file(docs_run_dir / "run_metadata.json")

    result = {
        "query": query,
        "selected_title": search_summary.get("selected_title"),
        "selected_company": search_summary.get("selected_company"),
        "selected_url": search_summary.get("selected_url"),
        "selected_is_full_jd": bool(search_summary.get("selected_is_full_jd", False)),
        "selected_confidence": clamp_confidence(search_summary.get("selected_confidence", 0.0)),
        "selected_jd_text_preview": str(search_summary.get("selected_jd_text_preview", "")).strip(),
        "url_import_succeeded": parse_markdown_bool(readme_values.get("URL Import Succeeded")),
        "used_fallback_jd": parse_markdown_bool(readme_values.get("Used Fallback JD Draft")),
        "analysis_succeeded": bool(analysis_summary.get("success", False)),
        "docs_run_dir": str(docs_run_dir).replace("\\", "/"),
        "notes": [],
        "extra_notes": [],
        "search_failed": False,
        "readme_values": readme_values,
        "run_metadata": run_metadata,
    }
    result["notes"] = build_run_notes(result)
    result["status"] = classify_run_result(result)
    result.pop("extra_notes", None)
    result.pop("readme_values", None)
    result.pop("run_metadata", None)
    return result


def build_failed_run_result(
    query: str,
    *,
    docs_run_dir: Path | None = None,
    extra_notes: list[str] | None = None,
) -> dict[str, Any]:
    result = {
        "query": query,
        "selected_title": None,
        "selected_company": None,
        "selected_url": None,
        "selected_is_full_jd": False,
        "selected_confidence": 0.0,
        "selected_jd_text_preview": "",
        "url_import_succeeded": None,
        "used_fallback_jd": None,
        "analysis_succeeded": False,
        "docs_run_dir": str(docs_run_dir).replace("\\", "/") if docs_run_dir else None,
        "search_failed": True,
        "extra_notes": extra_notes or [],
    }
    result["notes"] = build_run_notes(result)
    result["status"] = classify_run_result(result)
    result.pop("extra_notes", None)
    return result


def run_single_experiment(args: argparse.Namespace, query: str, project_root: Path) -> dict[str, Any]:
    publish_dir = Path(args.publish_docs_dir)
    known_dir_names = {path.name for path in list_timestamp_dirs(publish_dir)}
    command = build_demo_command(args, query, project_root)

    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=get_subprocess_timeout(args.timeout_seconds),
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        docs_run_dir = find_new_publish_dir(publish_dir, known_dir_names)
        return build_failed_run_result(
            query,
            docs_run_dir=docs_run_dir,
            extra_notes=["demo_gemini_search_flow.py timed out."],
        )
    except OSError as exc:
        docs_run_dir = find_new_publish_dir(publish_dir, known_dir_names)
        return build_failed_run_result(
            query,
            docs_run_dir=docs_run_dir,
            extra_notes=[f"demo_gemini_search_flow.py failed to start: {exc}"],
        )

    docs_run_dir = find_new_publish_dir(publish_dir, known_dir_names)
    if docs_run_dir is None:
        notes = [f"demo_gemini_search_flow.py exited with code {completed.returncode}."]
        if completed.stderr.strip():
            notes.append(f"stderr: {completed.stderr.strip()}")
        return build_failed_run_result(query, extra_notes=notes)

    if completed.returncode != 0:
        result = load_run_result(query, docs_run_dir)
        result["notes"].append(f"demo_gemini_search_flow.py exited with code {completed.returncode}.")
        result["status"] = classify_run_result(result)
        return result
    return load_run_result(query, docs_run_dir)


def build_experiment_summary(run_results: list[dict[str, Any]]) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    good_runs = sum(1 for result in run_results if result["status"] == GOOD_STATUS)
    partial_runs = sum(1 for result in run_results if result["status"] == PARTIAL_STATUS)
    failed_runs = sum(1 for result in run_results if result["status"] == FAILED_STATUS)
    url_import_attempts = sum(
        1 for result in run_results if result.get("url_import_succeeded") is not None
    )
    url_import_successes = sum(
        1 for result in run_results if result.get("url_import_succeeded") is True
    )
    full_jd_runs = sum(1 for result in run_results if result.get("selected_is_full_jd") is True)
    confidence_good_runs = sum(
        1 for result in run_results if clamp_confidence(result.get("selected_confidence")) >= 0.7
    )
    runs_with_url = sum(1 for result in run_results if str(result.get("selected_url", "")).strip())
    sanitized_runs = [sanitize_run_for_summary(result) for result in run_results]

    return {
        "generated_at": generated_at,
        "total_runs": len(run_results),
        "good_runs": good_runs,
        "partial_runs": partial_runs,
        "failed_runs": failed_runs,
        "runs_with_selected_url": runs_with_url,
        "full_jd_runs": full_jd_runs,
        "high_confidence_runs": confidence_good_runs,
        "url_import_attempts": url_import_attempts,
        "url_import_successes": url_import_successes,
        "runs": sanitized_runs,
    }


def build_json_summary(run_results: list[dict[str, Any]]) -> dict[str, Any]:
    return build_experiment_summary(run_results)


def sanitize_run_for_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": run.get("query"),
        "status": run.get("status"),
        "selected_title": run.get("selected_title"),
        "selected_company": run.get("selected_company"),
        "selected_url": run.get("selected_url"),
        "selected_is_full_jd": bool(run.get("selected_is_full_jd", False)),
        "selected_confidence": clamp_confidence(run.get("selected_confidence", 0.0)),
        "url_import_succeeded": run.get("url_import_succeeded"),
        "used_fallback_jd": run.get("used_fallback_jd"),
        "analysis_succeeded": run.get("analysis_succeeded"),
        "docs_run_dir": run.get("docs_run_dir"),
        "notes": [str(note) for note in run.get("notes", []) if str(note).strip()],
    }


def build_markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Real Gemini JD Experiment Summary",
        "",
        f"- Generated At: {summary['generated_at']}",
        f"- Total Queries: {summary['total_runs']}",
        f"- GOOD Runs: {summary['good_runs']}",
        f"- PARTIAL Runs: {summary['partial_runs']}",
        f"- FAILED Runs: {summary['failed_runs']}",
        "",
        "## Runs",
        "",
        "| Query | Success | Selected Title | Company | URL | is_full_jd | confidence | URL Import Succeeded | Used Fallback | Analyze Succeeded | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for run in summary["runs"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(run.get("query")),
                    _markdown_cell(run.get("status")),
                    _markdown_cell(run.get("selected_title")),
                    _markdown_cell(run.get("selected_company")),
                    _markdown_cell(run.get("selected_url")),
                    _markdown_cell(run.get("selected_is_full_jd")),
                    _markdown_cell(run.get("selected_confidence")),
                    _markdown_cell(run.get("url_import_succeeded")),
                    _markdown_cell(run.get("used_fallback_jd")),
                    _markdown_cell(run.get("analysis_succeeded")),
                    _markdown_cell("; ".join(run.get("notes", []))),
                ]
            )
            + " |"
        )

    url_import_attempts = summary["url_import_attempts"]
    url_import_successes = summary["url_import_successes"]
    import_success_rate = (
        f"{url_import_successes}/{url_import_attempts}"
        if url_import_attempts
        else "0/0"
    )
    needs_quality_upgrade = summary["good_runs"] == 0 or summary["partial_runs"] >= summary["good_runs"]

    lines.extend(
        [
            "",
            "## Preliminary Assessment",
            "",
            f"- Gemini CLI stable at finding job URLs: {'yes' if summary['runs_with_selected_url'] == summary['total_runs'] and summary['total_runs'] > 0 else 'not yet'}",
            f"- Gemini CLI stable at returning full JD: {'yes' if summary['full_jd_runs'] == summary['total_runs'] and summary['total_runs'] > 0 else 'not yet'}",
            f"- URL import success rate: {import_success_rate}",
            f"- Need JD Acquisition Quality Upgrade next: {'yes' if needs_quality_upgrade else 'not yet'}",
            "",
            "## Classification Rules",
            "",
            "- GOOD: analyze success = true, selected_url is non-empty, selected_confidence >= 0.7, selected_is_full_jd = true",
            "- PARTIAL: analyze success = true, but full JD / confidence / fallback conditions are not ideal",
            "- FAILED: search failed, analyze failed, or no selected item was returned",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    return text.replace("|", "\\|")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_real_experiments(args: argparse.Namespace) -> int:
    project_root = Path(__file__).resolve().parents[1]
    queries = load_queries(args.queries, args.query_file, max_runs=args.max_runs)
    run_results: list[dict[str, Any]] = []

    for index, query in enumerate(queries):
        if index > 0:
            time.sleep(1)
        run_results.append(run_single_experiment(args, query, project_root))

    publish_dir = Path(args.publish_docs_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)
    summary = build_json_summary(run_results)
    write_text(publish_dir / SUMMARY_MARKDOWN_NAME, build_markdown_summary(summary))
    write_json(publish_dir / SUMMARY_JSON_NAME, summary)

    return 0 if all(result["status"] != FAILED_STATUS for result in run_results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_real_experiments(args)


if __name__ == "__main__":
    raise SystemExit(main())
