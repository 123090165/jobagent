from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT_DIR = "demo_runs"
DEFAULT_PUBLISH_DOCS_DIR = "docs/demo_runs"
DEFAULT_TIMEOUT_SECONDS = 30
HEALTHCHECK_MAX_ATTEMPTS = 10
HEALTHCHECK_INTERVAL_SECONDS = 1
REPORT_EXCERPT_MAX_CHARS = 1200
SEARCH_SNIPPET_PREVIEW_MAX_CHARS = 300
SCRIPT_VERSION = "v1"
ALLOWED_RESUME_SUFFIXES = {".txt", ".md"}


class DemoFlowError(ValueError):
    """User-facing runtime error for the demo flow script."""


class ApiRequestError(DemoFlowError):
    def __init__(
        self,
        endpoint: str,
        status_code: int | None,
        response_data: dict[str, Any],
    ) -> None:
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_data = response_data
        detail = response_data.get("detail", f"Request to {endpoint} failed")
        super().__init__(str(detail))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a safe Gemini search -> JD import -> full analysis demo flow.",
    )
    parser.add_argument("--query", required=True, help="Search query sent to /search/jobs.")
    parser.add_argument(
        "--resume-file",
        required=True,
        help="Path to a local .txt or .md resume file.",
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help=f"FastAPI base URL. Default: {DEFAULT_API_BASE_URL}",
    )
    parser.add_argument(
        "--start-api",
        action="store_true",
        help="Start the local FastAPI server before running the demo.",
    )
    parser.add_argument(
        "--try-import-url",
        action="store_true",
        help="Try /jobs/import-url when the selected search item includes a URL.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable all LLM flags in /analyze/full.",
    )
    parser.add_argument(
        "--use-langgraph",
        action="store_true",
        help="Enable the LangGraph workflow in /analyze/full.",
    )
    parser.add_argument(
        "--save-result",
        action="store_true",
        help="Allow /analyze/full to save into SQLite. Default is false.",
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
        "--publish-sanitized",
        action="store_true",
        help="Write sanitized summaries to docs/demo_runs/<timestamp>/.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP request timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    return parser


def validate_resume_file(resume_file: str | Path) -> str:
    path = Path(resume_file)
    if not path.exists():
        raise DemoFlowError(f"Resume file does not exist: {path}")
    if path.suffix.lower() not in ALLOWED_RESUME_SUFFIXES:
        raise DemoFlowError("Resume file must be a .txt or .md file")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DemoFlowError("Resume file must be UTF-8 text") from exc

    if not text.strip():
        raise DemoFlowError("Resume file cannot be empty")
    return text


def create_demo_output_dir(base_dir: str | Path, timestamp: str | None = None) -> Path:
    stamp = timestamp or build_timestamp()
    output_dir = Path(base_dir) / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def create_publish_output_dir(base_dir: str | Path, timestamp: str | None = None) -> Path:
    stamp = timestamp or build_timestamp()
    output_dir = Path(base_dir) / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def build_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_fallback_jd_text(item: dict[str, Any]) -> str:
    title = str(item.get("title", "")).strip() or "Unknown Title"
    company = str(item.get("company", "")).strip() or "Unknown Company"
    location = str(item.get("location", "")).strip() or "Unknown Location"
    snippet = str(item.get("snippet", "")).strip() or "No snippet provided."
    url = str(item.get("url", "")).strip() or "No source URL provided."
    return (
        "Fallback JD Draft\n"
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {location}\n"
        f"Source URL: {url}\n\n"
        "Snippet:\n"
        f"{snippet}\n"
    )


def select_first_search_item(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise DemoFlowError("Search returned no items")
    if not isinstance(items[0], dict):
        raise DemoFlowError("Selected search item is invalid")
    return items[0]


def build_analysis_payload(
    resume_text: str,
    jd_text: str,
    *,
    use_llm: bool = False,
    use_langgraph: bool = False,
    save_result: bool = False,
) -> dict[str, Any]:
    return {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "use_llm_jd": use_llm,
        "use_llm_resume_optimize": use_llm,
        "use_llm_project_challenge": use_llm,
        "use_langgraph_workflow": use_langgraph,
        "save_result": save_result,
    }


def build_sanitized_search_summary(
    query: str,
    payload: dict[str, Any],
    selected_item: dict[str, Any],
) -> dict[str, Any]:
    items = payload.get("items", [])
    snippet_preview = str(selected_item.get("snippet", ""))[:SEARCH_SNIPPET_PREVIEW_MAX_CHARS]
    return {
        "query": query,
        "provider": payload.get("provider", "gemini_cli"),
        "item_count": len(items) if isinstance(items, list) else 0,
        "selected_title": selected_item.get("title"),
        "selected_company": selected_item.get("company"),
        "selected_location": selected_item.get("location"),
        "selected_url": selected_item.get("url"),
        "selected_source": selected_item.get("source"),
        "selected_snippet_preview": snippet_preview,
    }


def build_sanitized_analysis_summary(
    analysis_response: dict[str, Any] | None,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings = warnings or []
    if not analysis_response:
        return {
            "success": False,
            "overall_score": None,
            "matched_skills": [],
            "missing_skills": [],
            "workflow_step_names": [],
            "workflow_modes": [],
            "record_id": None,
            "warnings": warnings,
        }

    match_report = analysis_response.get("match_report", {})
    workflow_steps = analysis_response.get("workflow_steps", [])
    resume_profile = analysis_response.get("resume_profile", {})
    job_analysis = analysis_response.get("job_analysis", {})

    resume_skills = {
        str(skill).strip()
        for skill in resume_profile.get("skills", [])
        if str(skill).strip()
    }
    required_skills = [
        str(skill).strip()
        for skill in job_analysis.get("required_skills", [])
        if str(skill).strip()
    ]
    matched_skills = [skill for skill in required_skills if skill in resume_skills][:20]
    missing_skills = [skill for skill in required_skills if skill not in resume_skills][:20]

    return {
        "success": True,
        "overall_score": match_report.get("overall_score"),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "workflow_step_names": [step.get("name") for step in workflow_steps if isinstance(step, dict)],
        "workflow_modes": [step.get("mode") for step in workflow_steps if isinstance(step, dict)],
        "record_id": analysis_response.get("record_id"),
        "warnings": warnings,
    }


def build_report_excerpt(
    analysis_response: dict[str, Any] | None,
    *,
    max_chars: int = REPORT_EXCERPT_MAX_CHARS,
) -> str:
    if not analysis_response:
        return ""

    lines = ["# Demo Report Excerpt"]
    job_analysis = analysis_response.get("job_analysis", {})
    match_report = analysis_response.get("match_report", {})
    resume_profile = analysis_response.get("resume_profile", {})
    workflow_steps = analysis_response.get("workflow_steps", [])

    title = job_analysis.get("job_title") or "Unknown Job"
    lines.append(f"- Job: {str(title)[:120]}")
    if match_report.get("overall_score") is not None:
        lines.append(f"- Overall Score: {match_report['overall_score']}")

    resume_skills = {
        str(skill).strip()
        for skill in resume_profile.get("skills", [])
        if str(skill).strip()
    }
    required_skills = [
        str(skill).strip()
        for skill in job_analysis.get("required_skills", [])
        if str(skill).strip()
    ]
    matched_skills = [skill for skill in required_skills if skill in resume_skills][:10]
    missing_skills = [skill for skill in required_skills if skill not in resume_skills][:10]

    lines.append("\n## Skill Snapshot")
    lines.append(f"- Matched Skills: {', '.join(matched_skills) if matched_skills else 'None'}")
    lines.append(f"- Missing Skills: {', '.join(missing_skills) if missing_skills else 'None'}")

    if workflow_steps:
        lines.append("\n## Workflow")
        lines.append(
            "- Steps: "
            + ", ".join(str(step.get("name", "")) for step in workflow_steps if isinstance(step, dict))
        )
        lines.append(
            "- Modes: "
            + ", ".join(str(step.get("mode", "")) for step in workflow_steps if isinstance(step, dict))
        )

    excerpt = "\n".join(lines).strip()
    if len(excerpt) > max_chars:
        return excerpt[: max_chars - 3].rstrip() + "..."
    return excerpt


def build_run_metadata(
    *,
    timestamp: str,
    api_base_url: str,
    query: str,
    start_api: bool,
    try_import_url: bool,
    use_llm: bool,
    use_langgraph: bool,
    save_result: bool,
    gemini_cli_command_overridden: bool = False,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "script_version": SCRIPT_VERSION,
        "api_base_url": api_base_url,
        "query": query,
        "flags": {
            "start_api": start_api,
            "try_import_url": try_import_url,
            "use_llm": use_llm,
            "use_langgraph": use_langgraph,
            "save_result": save_result,
            "gemini_cli_command_overridden": gemini_cli_command_overridden,
        },
        "safety": {
            "resume_text_uploaded_to_gemini_cli": False,
            "database_write_default": False,
            "deletes_files": False,
            "shell_true": False,
        },
    }


def build_publish_readme(context: dict[str, Any]) -> str:
    analysis_success = context.get("analysis_success", False)
    warnings = context.get("warnings", [])
    limitations = [
        "This demo does not upload full resume_text to Gemini CLI.",
        "The script does not auto-save to SQLite unless --save-result is explicitly provided.",
        "Search results do not automatically trigger JD import or analysis outside this script.",
        "The published record is sanitized and does not include raw Gemini output or full JD text.",
    ]
    suggestions = [
        "Add a JobImportCandidate review step before any future storage or analysis automation.",
        "Keep URL import optional and user-confirmed for provider outputs with weak snippets.",
        "Consider richer sanitized step summaries if future demo reviews need more observability.",
    ]

    lines = [
        "# Gemini Search Demo Run",
        "",
        f"- Timestamp: {context['timestamp']}",
        f"- Query: {context['query']}",
        f"- GeminiCLIProvider Enabled: {context.get('gemini_provider_enabled', True)}",
        f"- Tried URL Import: {context.get('try_import_url', False)}",
        f"- URL Import Succeeded: {context.get('jd_import_success')}",
        f"- Used Fallback JD Draft: {context.get('used_fallback_jd')}",
        f"- /analyze/full Succeeded: {analysis_success}",
        f"- Used LLM: {context.get('use_llm', False)}",
        f"- Used LangGraph: {context.get('use_langgraph', False)}",
        f"- save_result: {context.get('save_result', False)}",
        f"- Gemini CLI Command Overridden: {context.get('gemini_cli_command_overridden', False)}",
        f"- Raw Output Directory: {context.get('raw_output_dir')}",
        "",
        "## Current Limitations",
    ]
    lines.extend(f"- {item}" for item in limitations)
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    lines.append("## Follow-up Suggestions")
    lines.extend(f"- {item}" for item in suggestions)
    return "\n".join(lines).strip() + "\n"


def build_summary_text(context: dict[str, Any]) -> str:
    lines = [
        f"timestamp={context['timestamp']}",
        f"query={context['query']}",
        f"analysis_success={context.get('analysis_success', False)}",
        f"jd_import_success={context.get('jd_import_success')}",
        f"used_fallback_jd={context.get('used_fallback_jd')}",
        f"raw_output_dir={context.get('raw_output_dir')}",
    ]
    if context.get("warnings"):
        lines.append("warnings=" + " | ".join(context["warnings"]))
    if context.get("search_error"):
        lines.append("search_error=" + json.dumps(context["search_error"], ensure_ascii=False))
    if context.get("analysis_error"):
        lines.append("analysis_error=" + json.dumps(context["analysis_error"], ensure_ascii=False))
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: int,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return _parse_json_body(body, url)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        response_data = _parse_error_body(body, exc.code)
        raise ApiRequestError(url, exc.code, response_data) from exc
    except URLError as exc:
        raise DemoFlowError(f"Failed to reach API endpoint: {url}") from exc


def _parse_json_body(body: str, url: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DemoFlowError(f"API response from {url} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DemoFlowError(f"API response from {url} must be a JSON object")
    return payload


def _parse_error_body(body: str, status_code: int) -> dict[str, Any]:
    with suppress(json.JSONDecodeError):
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed
    return {
        "detail": body or f"HTTP {status_code}",
        "error_code": None,
        "status_code": status_code,
    }


def healthcheck_api(base_url: str, *, timeout_seconds: int, max_attempts: int = 1) -> dict[str, Any]:
    last_error: Exception | None = None
    health_url = f"{base_url.rstrip('/')}/health"
    for attempt in range(max_attempts):
        try:
            return request_json("GET", health_url, timeout_seconds=timeout_seconds)
        except DemoFlowError as exc:
            last_error = exc
            if attempt < max_attempts - 1:
                time.sleep(HEALTHCHECK_INTERVAL_SECONDS)
    raise DemoFlowError(
        f"FastAPI health check failed at {health_url}. Start the API first or use --start-api."
    ) from last_error


def start_api_process(project_root: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["JOBAGENT_ENABLE_GEMINI_CLI"] = "1"
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    return subprocess.Popen(
        command,
        cwd=project_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        shell=False,
    )


def terminate_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def publish_sanitized_artifacts(context: dict[str, Any]) -> None:
    publish_dir = context.get("publish_dir")
    if not publish_dir:
        return

    publish_path = Path(publish_dir)
    write_json(publish_path / "run_metadata.json", context["run_metadata"])
    write_text(publish_path / "README.md", build_publish_readme(context))

    if context.get("search_response") and context.get("selected_item"):
        write_json(
            publish_path / "search_summary.json",
            build_sanitized_search_summary(
                context["query"],
                context["search_response"],
                context["selected_item"],
            ),
        )

    if context.get("analysis_response") or context.get("analysis_error"):
        analysis_source = context.get("analysis_response")
        analysis_summary = build_sanitized_analysis_summary(
            analysis_source,
            warnings=context.get("warnings", []),
        )
        if context.get("analysis_error"):
            analysis_summary["success"] = False
        write_json(publish_path / "analysis_summary.json", analysis_summary)

    report_excerpt = build_report_excerpt(context.get("analysis_response"))
    if report_excerpt:
        write_text(publish_path / "report_excerpt.md", report_excerpt)


def run_demo_flow(args: argparse.Namespace) -> int:
    project_root = Path(__file__).resolve().parents[1]
    timestamp = build_timestamp()
    output_dir = create_demo_output_dir(args.output_dir, timestamp)
    publish_dir = (
        create_publish_output_dir(args.publish_docs_dir, timestamp)
        if args.publish_sanitized
        else None
    )

    run_metadata = build_run_metadata(
        timestamp=timestamp,
        api_base_url=args.api_base_url,
        query=args.query,
        start_api=args.start_api,
        try_import_url=args.try_import_url,
        use_llm=args.use_llm,
        use_langgraph=args.use_langgraph,
        save_result=args.save_result,
        gemini_cli_command_overridden=bool(os.getenv("JOBAGENT_GEMINI_CLI_COMMAND")),
    )
    context: dict[str, Any] = {
        "timestamp": timestamp,
        "query": args.query,
        "api_base_url": args.api_base_url,
        "start_api": args.start_api,
        "try_import_url": args.try_import_url,
        "use_llm": args.use_llm,
        "use_langgraph": args.use_langgraph,
        "save_result": args.save_result,
        "gemini_provider_enabled": True,
        "gemini_cli_command_overridden": bool(os.getenv("JOBAGENT_GEMINI_CLI_COMMAND")),
        "raw_output_dir": str(output_dir),
        "publish_dir": str(publish_dir) if publish_dir else None,
        "run_metadata": run_metadata,
        "warnings": [],
        "jd_import_success": None,
        "used_fallback_jd": None,
        "analysis_success": False,
    }

    api_process: subprocess.Popen[str] | None = None
    try:
        resume_text = validate_resume_file(args.resume_file)

        if args.start_api:
            api_process = start_api_process(project_root)
            healthcheck_api(
                args.api_base_url,
                timeout_seconds=args.timeout_seconds,
                max_attempts=HEALTHCHECK_MAX_ATTEMPTS,
            )
        else:
            healthcheck_api(
                args.api_base_url,
                timeout_seconds=args.timeout_seconds,
                max_attempts=1,
            )

        search_response = request_json(
            "POST",
            f"{args.api_base_url.rstrip('/')}/search/jobs",
            payload={"query": args.query, "provider": "gemini_cli", "limit": 5},
            timeout_seconds=args.timeout_seconds,
        )
        context["search_response"] = search_response
        write_json(output_dir / "search_response.json", search_response)

        selected_item = select_first_search_item(search_response)
        context["selected_item"] = selected_item
        write_json(output_dir / "selected_search_item.json", selected_item)

        fallback_jd_text = build_fallback_jd_text(selected_item)
        jd_text = fallback_jd_text
        context["used_fallback_jd"] = True

        if args.try_import_url and str(selected_item.get("url", "")).strip():
            try:
                jd_import_response = request_json(
                    "POST",
                    f"{args.api_base_url.rstrip('/')}/jobs/import-url",
                    payload={"url": selected_item["url"]},
                    timeout_seconds=args.timeout_seconds,
                )
                context["jd_import_success"] = True
                context["used_fallback_jd"] = False
                context["jd_import_response"] = jd_import_response
                jd_text = str(jd_import_response.get("extracted_text", "")).strip() or fallback_jd_text
                write_json(output_dir / "jd_import_response.json", jd_import_response)
            except ApiRequestError as exc:
                context["jd_import_success"] = False
                context["jd_import_error"] = exc.response_data
                warning = (
                    "JD URL import failed: "
                    f"{exc.response_data.get('detail')} ({exc.response_data.get('error_code')})"
                )
                context["warnings"].append(warning)
                write_json(output_dir / "jd_import_error.json", exc.response_data)

        write_text(output_dir / "jd_text.txt", jd_text)

        analysis_payload = build_analysis_payload(
            resume_text,
            jd_text,
            use_llm=args.use_llm,
            use_langgraph=args.use_langgraph,
            save_result=args.save_result,
        )
        analysis_response = request_json(
            "POST",
            f"{args.api_base_url.rstrip('/')}/analyze/full",
            payload=analysis_payload,
            timeout_seconds=args.timeout_seconds,
        )
        context["analysis_response"] = analysis_response
        context["analysis_success"] = True
        write_json(output_dir / "analysis_response.json", analysis_response)

        markdown_report = str(analysis_response.get("markdown_report", "")).strip()
        if markdown_report:
            write_text(output_dir / "report.md", markdown_report)

        write_text(output_dir / "summary.txt", build_summary_text(context))
        publish_sanitized_artifacts(context)
        return 0

    except ApiRequestError as exc:
        if exc.endpoint.endswith("/search/jobs"):
            context["search_error"] = exc.response_data
            write_json(output_dir / "search_error.json", exc.response_data)
            print(
                f"/search/jobs failed: {exc.response_data.get('detail')} "
                f"({exc.response_data.get('error_code')})",
                file=sys.stderr,
            )
        elif exc.endpoint.endswith("/analyze/full"):
            context["analysis_error"] = exc.response_data
            write_json(output_dir / "analysis_error.json", exc.response_data)
            print(
                f"/analyze/full failed: {exc.response_data.get('detail')} "
                f"({exc.response_data.get('error_code')})",
                file=sys.stderr,
            )
        else:
            context["warnings"].append(str(exc))
        write_text(output_dir / "summary.txt", build_summary_text(context))
        publish_sanitized_artifacts(context)
        return 1
    except KeyboardInterrupt:
        context["warnings"].append("Interrupted by user")
        write_text(output_dir / "summary.txt", build_summary_text(context))
        publish_sanitized_artifacts(context)
        return 130
    except DemoFlowError as exc:
        context["warnings"].append(str(exc))
        write_text(output_dir / "summary.txt", build_summary_text(context))
        publish_sanitized_artifacts(context)
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        terminate_process(api_process)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_demo_flow(args)


if __name__ == "__main__":
    raise SystemExit(main())
