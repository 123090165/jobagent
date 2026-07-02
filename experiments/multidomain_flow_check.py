from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.resumes.multidomain_flow_cases import (
    MULTIDOMAIN_FLOW_CASES,
    MultidomainFlowCase,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multidomain resume-to-search-preview flow checks.")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "experiments" / "output"),
        help="Directory for the Markdown report.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{timestamp}_multidomain_flow_check.md"

    with tempfile.TemporaryDirectory(prefix="jobagent_multidomain_", ignore_cleanup_errors=True) as temp_dir:
        os.environ["JOBAGENT_DB_PATH"] = str(Path(temp_dir) / "multidomain_flow.sqlite3")
        client = TestClient(app)
        try:
            results = [_run_case(client, case) for case in MULTIDOMAIN_FLOW_CASES]
        finally:
            client.close()

    output_path.write_text(_render_markdown(results), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


def _run_case(client: TestClient, case: MultidomainFlowCase) -> dict[str, Any]:
    resume_text = case.path.read_text(encoding="utf-8")
    session = client.post("/api/v1/profile-sessions").json()
    session_id = session["session_id"]
    client.post(f"/api/v1/profile-sessions/{session_id}/resume-text", json={"text": resume_text})
    review = client.post(f"/api/v1/profile-sessions/{session_id}/parse-resume").json()["parsed_review"]
    draft = client.post(f"/api/v1/profile-sessions/{session_id}/profile-draft").json()["profile_draft"]
    confirmed = client.post(f"/api/v1/profile-drafts/{draft['profile_draft_id']}/confirm").json()[
        "confirmed_profile"
    ]
    preview = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "local_mock",
            "max_results": 10,
        },
    ).json()
    intent = preview["search_intent"]
    checks = _build_checks(case, confirmed, preview)
    return {
        "case": case,
        "review": review,
        "draft": draft,
        "confirmed": confirmed,
        "preview": preview,
        "intent": intent,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
    }


def _build_checks(
    case: MultidomainFlowCase,
    confirmed: dict[str, Any],
    preview: dict[str, Any],
) -> list[dict[str, object]]:
    intent = preview["search_intent"]
    role_values = confirmed["target_roles"]
    direction_values = confirmed["target_directions"]
    intent_values = (
        intent["industry_domains"]
        + intent["evidence_skills"]
        + preview["provider_queries"]
    )
    combined = " ".join(
        role_values
        + direction_values
        + confirmed["search_keywords"]
        + preview["provider_queries"]
        + intent["role_titles"]
        + intent["industry_domains"]
        + intent["evidence_skills"]
    ).lower()
    checks = [
        {
            "name": "expected role signal present",
            "passed": _has_any(role_values, case.expected_role_terms),
            "details": ", ".join(case.expected_role_terms),
        },
        {
            "name": "expected direction signal present",
            "passed": _has_any(direction_values, case.expected_direction_terms),
            "details": ", ".join(case.expected_direction_terms),
        },
        {
            "name": "expected intent/query signal present",
            "passed": _has_any(intent_values, case.expected_intent_terms),
            "details": ", ".join(case.expected_intent_terms),
        },
    ]
    for forbidden in case.forbidden_terms:
        checks.append(
            {
                "name": f"forbidden drift absent: {forbidden}",
                "passed": forbidden.lower() not in combined,
                "details": forbidden,
            }
        )
    return checks


def _has_any(values: list[str], terms: tuple[str, ...]) -> bool:
    combined = " ".join(values).lower()
    return any(term.lower() in combined for term in terms)


def _render_markdown(results: list[dict[str, Any]]) -> str:
    passed_count = sum(1 for result in results if result["passed"])
    lines = [
        "# Multidomain JobAgent Flow Check",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Cases: {passed_count}/{len(results)} passed",
        "",
        "This report runs synthetic multidomain resumes through resume review, profile draft, confirmation, and search preview. It does not call real job providers or real LLM APIs.",
        "",
    ]
    for result in results:
        case: MultidomainFlowCase = result["case"]
        review = result["review"]
        confirmed = result["confirmed"]
        preview = result["preview"]
        intent = result["intent"]
        status = "PASS" if result["passed"] else "FAIL"
        lines.extend(
            [
                f"## {case.case_id} - {status}",
                "",
                f"Source file: `{case.filename}`",
                "",
                "### Resume Review",
                f"- target_signals: {_fmt(review['target_signals'][:8])}",
                f"- skills: {_fmt(review['skills']['items'][:12])}",
                f"- quality_warnings: {_fmt(review['quality_warnings'])}",
                "",
                "### Confirmed Profile",
                f"- target_roles: {_fmt(confirmed['target_roles'])}",
                f"- target_directions: {_fmt(confirmed['target_directions'])}",
                f"- core_skills: {_fmt(confirmed['core_skills'])}",
                f"- search_keywords: {_fmt(confirmed['search_keywords'][:14])}",
                f"- preferred_locations: {_fmt(confirmed['preferred_locations'])}",
                "",
                "### Search Intent",
                f"- role_titles: {_fmt(intent['role_titles'])}",
                f"- role_families: {_fmt(intent['role_families'])}",
                f"- industry_domains: {_fmt(intent['industry_domains'])}",
                f"- evidence_skills: {_fmt(intent['evidence_skills'])}",
                f"- generic_tools: {_fmt(intent['generic_tools'])}",
                "",
                "### Provider Queries",
            ]
        )
        for index, query in enumerate(preview["provider_queries"][:10], start=1):
            lines.append(f"{index}. {query}")
        lines.extend(["", "### Checks"])
        for check in result["checks"]:
            marker = "PASS" if check["passed"] else "FAIL"
            lines.append(f"- {marker}: {check['name']} ({check['details']})")
        lines.append("")
    return "\n".join(lines)


def _fmt(values: list[Any]) -> str:
    if not values:
        return "None"
    return ", ".join(str(value) for value in values)


if __name__ == "__main__":
    raise SystemExit(main())
