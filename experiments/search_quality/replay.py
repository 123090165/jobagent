"""用脚本化 Provider 离线重放完整搜索流水线，采集结果后交给指标模块评估。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.application.job_search_usecases import (
    create_job_search_run,
    execute_job_search_run,
    preview_job_search_run,
)
from app.main import app
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers.base import (
    JobSearchProviderError,
    RawJobCandidate,
)
from experiments.search_quality.metrics import (
    constraint_violation_at_5,
    duplicate_at_5,
    eligible_pool_recall,
    filled_slots_at_5,
    ndcg_at_5,
    pool_recall,
    precision_at_5,
)
from experiments.search_quality.report import finalize_manifest, render_markdown, stable_digest
from experiments.search_quality.schemas import EvaluationCase, FixtureCorpus


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "search_quality_v2" / "cases.json"
DEFAULT_BASELINE = Path(__file__).parent / "baselines" / "v2_iteration1.json"
RUNTIME_PROFILE = "search_v2_iteration1_deterministic"
TRACE_STEP_NAMES = (
    "Search planning",
    "Provider search",
    "Candidate filtering",
    "JD analysis",
    "Profile matching",
    "Result assembly",
)


class TrapLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise AssertionError("offline replay must not call an LLM")


class ScriptedReplayProvider:
    """把scriptedreplay接入统一 Provider 协议。"""
    provider_kind = "fixture"

    def __init__(self, case: EvaluationCase, *, allowed_queries: list[str]):
        self.case = case
        self.allowed_queries = frozenset(allowed_queries)
        sources = sorted(case.selected_sources)
        self.provider_name = sources[0] if len(sources) == 1 else f"multi_source:{','.join(sources)}"
        self.returned_candidate_ids: list[str] = []
        self.source_attempts: list[dict[str, object]] = []

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        if query not in self.allowed_queries:
            raise JobSearchProviderError(f"undeclared scripted query: {query!r}")

        candidate_ids: list[str] = []
        for source in sorted(self.case.selected_sources):
            responses = [
                response
                for response in self.case.scripted_responses
                if response.source == source and response.location == location
            ]
            response = responses[0] if responses else None
            if response is None:
                raise JobSearchProviderError(
                    f"undeclared scripted key: {(source, query, location)!r}"
                )
            failed = response.error_code is not None
            self.source_attempts.append(
                {
                    "source": source,
                    "query": query,
                    "location": location,
                    "returned_count": 0 if failed else len(response.candidate_ids),
                    "error_code": response.error_code,
                }
            )
            if not failed:
                candidate_ids.extend(sorted(response.candidate_ids))

        payloads = self.case.payload_map()
        candidates: list[RawJobCandidate] = []
        for rank, candidate_id in enumerate(candidate_ids[:limit], start=1):
            payload = payloads[candidate_id]
            raw = payload.model_dump(exclude={"candidate_id"})
            raw["provider_warnings"] = list(raw["provider_warnings"])
            raw["discovery_query"] = query
            raw["discovery_rank"] = rank
            candidates.append(RawJobCandidate.model_validate(raw))
            self.returned_candidate_ids.append(candidate_id)
        return candidates


def load_corpus(path: Path = DEFAULT_FIXTURE) -> FixtureCorpus:
    return FixtureCorpus.model_validate_json(path.read_text(encoding="utf-8"))


def run_replay(
    corpus: FixtureCorpus,
    *,
    case_ids: set[str] | None = None,
    baseline_id: str = "v2_iteration1",
    runtime_profile: str = RUNTIME_PROFILE,
    provider_query_limit: int = 6,
) -> dict[str, Any]:
    selected = [case for case in corpus.cases if not case_ids or case.case_id in case_ids]
    if case_ids:
        missing = case_ids - {case.case_id for case in selected}
        if missing:
            raise ValueError(f"unknown replay case ids: {sorted(missing)}")

    previous_db = os.environ.get("JOBAGENT_DB_PATH")
    previous_langfuse = os.environ.get("JOBAGENT_LANGFUSE_ENABLED")
    try:
        os.environ["JOBAGENT_LANGFUSE_ENABLED"] = "false"
        with tempfile.TemporaryDirectory(
            prefix="jobagent_search_replay_",
            ignore_cleanup_errors=True,
        ) as temp_dir:
            os.environ["JOBAGENT_DB_PATH"] = str(Path(temp_dir) / "replay.sqlite3")
            with TestClient(app) as client:
                case_reports = [_run_case(client, case) for case in selected]
    finally:
        if previous_db is None:
            os.environ.pop("JOBAGENT_DB_PATH", None)
        else:
            os.environ["JOBAGENT_DB_PATH"] = previous_db
        if previous_langfuse is None:
            os.environ.pop("JOBAGENT_LANGFUSE_ENABLED", None)
        else:
            os.environ["JOBAGENT_LANGFUSE_ENABLED"] = previous_langfuse

    fixture_payload = json.loads(corpus.model_dump_json())
    manifest = {
        "schema_version": "search-quality-baseline-v1",
        "baseline_id": baseline_id,
        "execution_mode": "offline_replay",
        "runtime_profile": runtime_profile,
        "fixture_version": corpus.corpus_version,
        "fixture_digest": stable_digest(fixture_payload),
        "git_commit": _git_commit(),
        "case_count": len(case_reports),
        "configuration": {
            "analysis_mode": "deterministic",
            "use_llm": False,
            "max_results": 5,
            "provider_query_limit": provider_query_limit,
        },
        "cases": case_reports,
        "measurement_notes": [
            "Offline fixture timing is intentionally excluded.",
            "Additional deterministic planner queries alias the case's versioned explicit response payloads.",
        ],
    }
    return finalize_manifest(manifest)


def _run_case(client: TestClient, case: EvaluationCase) -> dict[str, Any]:
    session_id = _create_confirmed_session(client, case)
    client.put(f"/api/v1/profile-sessions/{session_id}/search-mission", json=case.system_input["search_mission"])
    client.post(
        f"/api/v1/profile-sessions/{session_id}/search-mission/interpret",
        json={"use_llm": False},
    )
    client.post(f"/api/v1/profile-sessions/{session_id}/search-mission/confirm")

    request_payload = dict(case.system_input["search_request"])
    request_payload["session_id"] = session_id
    request = JobSearchRunCreateRequest.model_validate(request_payload)
    preview = preview_job_search_run(request, llm_service=TrapLLM())
    planned_queries = preview.provider_queries
    provider = ScriptedReplayProvider(case, allowed_queries=planned_queries)

    created = create_job_search_run(
        request,
        job_search_provider=provider,
        llm_service=TrapLLM(),
    )
    completed = execute_job_search_run(
        created.job_search_run.job_search_run_id,
        job_search_provider=provider,
        llm_service=TrapLLM(),
        analysis_mode="deterministic",
        max_results=5,
    )
    steps = completed.steps
    if tuple(step.name for step in steps) != TRACE_STEP_NAMES:
        raise AssertionError("offline replay trace contract changed")

    url_to_id = {
        payload.source_url: payload.candidate_id
        for payload in case.candidate_payloads
        if payload.source_url
    }
    top_ids = [
        url_to_id[result.source_url]
        for result in completed.job_search_run.results[:5]
        if result.source_url in url_to_id
    ]
    pool_ids = list(dict.fromkeys(provider.returned_candidate_ids))
    metrics = {
        "pool_recall": pool_recall(case, pool_ids).model_dump(mode="json"),
        "eligible_pool_recall": eligible_pool_recall(case, pool_ids).model_dump(mode="json"),
        "precision_at_5": precision_at_5(case, top_ids).model_dump(mode="json"),
        "filled_slots_at_5": filled_slots_at_5(top_ids).model_dump(mode="json"),
        "ndcg_at_5": ndcg_at_5(case, top_ids).model_dump(mode="json"),
        "constraint_violation_at_5": constraint_violation_at_5(case, top_ids).model_dump(mode="json"),
        "duplicate_at_5": duplicate_at_5(case, top_ids).model_dump(mode="json"),
    }
    return {
        "case_id": case.case_id,
        "planned_queries": planned_queries,
        "pool_candidate_ids": pool_ids,
        "top_5_candidate_ids": top_ids,
        "trace_steps": [
            {
                "name": step.name,
                "mode": step.mode,
                "fallback_reason": step.fallback_reason,
            }
            for step in steps
        ],
        "source_attempts": provider.source_attempts,
        "metrics": metrics,
    }


def _create_confirmed_session(client: TestClient, case: EvaluationCase) -> str:
    profile = case.system_input["confirmed_profile"]
    resume_text = "\n".join(
        [
            "Synthetic Candidate",
            f"Summary: {profile['summary']}",
            f"Target roles: {', '.join(profile['target_roles'])}",
            f"Skills: {', '.join(profile['core_skills'])}",
            f"Supporting skills: {', '.join(profile['supporting_skills'])}",
            f"Preferred locations: {', '.join(profile['preferred_locations'])}",
        ]
    )
    session = client.post("/api/v1/profile-sessions").json()
    session_id = session["session_id"]
    client.post(
        f"/api/v1/profile-sessions/{session_id}/resume-text",
        json={"text": resume_text},
    ).raise_for_status()
    client.post(
        f"/api/v1/profile-sessions/{session_id}/parse-resume",
        params={"use_llm": False},
    ).raise_for_status()
    draft_response = client.post(
        f"/api/v1/profile-sessions/{session_id}/profile-draft"
    )
    draft_response.raise_for_status()
    draft_id = draft_response.json()["profile_draft"]["profile_draft_id"]
    client.post(f"/api/v1/profile-drafts/{draft_id}/confirm").raise_for_status()
    return session_id


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic offline search replay.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--baseline-id", default="v2_iteration1")
    parser.add_argument("--runtime-profile", default=RUNTIME_PROFILE)
    parser.add_argument("--provider-query-limit", type=int, default=6)
    args = parser.parse_args()

    manifest = run_replay(
        load_corpus(args.fixture),
        case_ids=set(args.case_id) or None,
        baseline_id=args.baseline_id,
        runtime_profile=args.runtime_profile,
        provider_query_limit=args.provider_query_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(manifest), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
