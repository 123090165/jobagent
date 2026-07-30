"""回归验证职位搜索 run、结果与 trace的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.application.job_search_usecases import create_job_search_run, execute_job_search_run
from app.main import app
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers.base import RawJobCandidate

client = TestClient(app)


class FakeProvider:
    """把fake接入统一 Provider 协议。"""
    provider_name = "mock"
    provider_kind = "mock"

    def search_jobs(self, *, query: str, location: str | None, limit: int):
        """提供 FakeProvider.search_jobs 所需的测试行为。"""
        base_location = location or "Remote"
        return [
            RawJobCandidate(
                title="Senior Backend Engineer",
                company="Example Systems",
                location=base_location,
                source_url="https://jobs.example.com/backend",
                source_provider=self.provider_name,
                snippet=f"Python FastAPI SQL platform APIs for query {query}",
                raw_description="Python FastAPI SQL APIs and backend platform services.",
                discovery_query=query,
                discovery_rank=1,
                detail_status="fake_inline",
            ),
            RawJobCandidate(
                title="AI Product Engineer",
                company="Prompt Harbor",
                location=base_location,
                source_url="https://jobs.example.com/ai-product",
                source_provider=self.provider_name,
                snippet=f"LLM product engineering and evaluations for query {query}",
                raw_description="LLM product engineering, prompt tooling, and evaluation workflows.",
                discovery_query=query,
                discovery_rank=2,
                detail_status="fake_inline",
            ),
        ][:limit]


class WideFakeProvider(FakeProvider):
    """把widefake接入统一 Provider 协议。"""
    def search_jobs(self, *, query: str, location: str | None, limit: int):
        """提供 WideFakeProvider.search_jobs 所需的测试行为。"""
        candidates = super().search_jobs(query=query, location=location, limit=2)
        return [
            *candidates,
            RawJobCandidate(
                title="Data Platform Intern",
                company="Warehouse Labs",
                location=location or "Remote",
                source_url="https://jobs.example.com/data-platform",
                source_provider=self.provider_name,
                snippet="SQL data pipelines and platform reliability.",
                raw_description="Build SQL data pipelines and improve platform reliability.",
                discovery_query=query,
                discovery_rank=3,
                detail_status="fake_inline",
            ),
        ]


class FakeJSONLLM:
    """为当前测试场景提供 FakeJSONLLM 夹具或替身。"""
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        """提供 FakeJSONLLM.chat_completion_json 所需的测试行为。"""
        if "ranked_candidates" in system_prompt:
            return {
                "ranked_candidates": [
                    {
                        "index": 1,
                        "match_score": 89,
                        "confidence_label": "strong",
                        "score_breakdown": {
                            "role_alignment": 22,
                            "domain_alignment": 24,
                            "skill_evidence": 18,
                            "seniority_and_work_type": 8,
                            "location_fit": 10,
                            "jd_evidence_quality": 10,
                            "risk_penalty": 3,
                        },
                        "matched_keywords": ["LLM", "evaluation"],
                        "match_reasons": ["LLM rubric preferred applied AI evidence."],
                        "risks": ["Backend API evidence is lighter."],
                        "evidence_quotes": ["LLM product engineering and evaluations"],
                    },
                    {
                        "index": 0,
                        "match_score": 73,
                        "confidence_label": "medium",
                        "score_breakdown": {
                            "role_alignment": 24,
                            "domain_alignment": 8,
                            "skill_evidence": 19,
                            "seniority_and_work_type": 8,
                            "location_fit": 10,
                            "jd_evidence_quality": 10,
                            "risk_penalty": 6,
                        },
                        "matched_keywords": ["Python", "FastAPI", "SQL"],
                        "match_reasons": ["Strong backend stack but weaker applied AI domain."],
                        "risks": ["May drift toward backend-only work."],
                        "evidence_quotes": ["Python FastAPI SQL APIs"],
                    },
                ],
                "quality_warnings": [],
            }
        return {
            "queries": ["Backend Engineer Python FastAPI", "AI Application Engineer LLM"],
            "locations": ["Remote", "Tokyo"],
            "target_roles": ["Backend Engineer", "AI Application Engineer"],
            "must_have_signals": ["Python", "FastAPI", "LLM"],
            "avoid_signals": [],
            "ranking_policy": "Prefer strong backend and applied AI overlap.",
            "quality_warnings": [],
        }


def _create_session_with_confirmed_profile(tmp_path, monkeypatch, name: str) -> dict:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / name))
    session = client.post("/api/v1/profile-sessions").json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={
            "text": (
                "Name: Jane Doe\n"
                "Role: Backend Engineer\n"
                "Skills: Python, FastAPI, SQL, Docker, LLM applications\n"
                "Project: Built agent evaluation and resume workflow tools.\n"
            )
        },
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume")
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft"
    ).json()
    return client.post(
        f"/api/v1/profile-drafts/{draft['profile_draft']['profile_draft_id']}/confirm"
    ).json()


def test_live_search_create_returns_running_or_completed(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-live-create.sqlite3")
    monkeypatch.setenv("JOBAGENT_JOB_SEARCH_PROVIDER", "mock")
    monkeypatch.setattr(
        "app.application.job_search_usecases.resolve_llm_provider",
        lambda provider=None: SimpleNamespace(
            provider=provider or "deepseek",
            service=FakeJSONLLM(),
            configured=True,
        ),
    )

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"], "search_mode": "live_search"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_search_run"]["status"] in {"running", "completed"}
    assert payload["job_search_run"]["search_mode"] == "live_search"
    assert len(payload["steps"]) == 6


def test_live_search_requires_confirmed_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-live-no-confirmed.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": session["session_id"], "search_mode": "live_search"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "confirmed_profile_required"


def test_execute_live_run_with_fake_provider_completes(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-live-exec.sqlite3")
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            use_llm=True,
            max_results=5,
        ),
        job_search_provider=FakeProvider(),
        llm_service=FakeJSONLLM(),
    )

    completed = execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        job_search_provider=FakeProvider(),
        llm_service=FakeJSONLLM(),
        max_results=5,
    )

    assert completed.job_search_run.status == "completed"
    assert completed.profile_session.current_step.value == "job_search_completed"
    assert completed.job_search_run.results
    assert all(item.source == "live_search" for item in completed.job_search_run.results)
    assert completed.job_search_run.results[0].company == "Prompt Harbor"
    assert completed.job_search_run.results[0].recall_score == 89
    assert completed.job_search_run.results[0].final_match_score == 76
    assert completed.job_search_run.results[0].match_score == 76
    assert completed.job_search_run.results[0].evidence_quotes
    assert completed.steps[-1].status == "completed"
    provider_step = next(step for step in completed.steps if step.name == "Provider search")
    assert provider_step.details["raw_candidate_count"] >= 2
    assert provider_step.details["deduped_candidate_count"] >= 2
    assert provider_step.details["missing_detail_count"] == 0
    assert provider_step.details["source_stats"][0]["source_provider"] == "mock"
    assert provider_step.details["source_stats"][0]["detail_coverage_rate"] == 1.0
    assert provider_step.details["query_stats"]


def test_live_run_steps_endpoint_returns_trace(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-live-steps.sqlite3")
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            use_llm=False,
            max_results=5,
        ),
        job_search_provider=FakeProvider(),
    )
    execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        job_search_provider=FakeProvider(),
        llm_service=FakeJSONLLM(),
        max_results=5,
    )

    response = client.get(f"/api/v1/job-search-runs/{run_response.job_search_run.job_search_run_id}/steps")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["name"] for item in items] == [
        "Search planning",
        "Provider search",
        "Candidate filtering",
        "JD analysis",
        "Profile matching",
        "Result assembly",
    ]
    assert items[0]["mode"] == "llm"
    assert "details" in items[1]
    assert items[1]["details"]["query_count"] >= 1
    assert "source_stats" in items[1]["details"]
    assert "logical_provider_call_count" in items[1]["details"]
    assert run_response.job_search_run.llm_enabled is True


def test_live_run_persists_bounded_candidate_pool_separately_from_final_results(
    monkeypatch,
    tmp_path,
) -> None:
    confirmed = _create_session_with_confirmed_profile(
        tmp_path,
        monkeypatch,
        "job-search-live-items.sqlite3",
    )
    provider = WideFakeProvider()
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            use_llm=False,
            max_results=1,
        ),
        job_search_provider=provider,
    )
    run_id = run_response.job_search_run.job_search_run_id
    assert client.get("/api/v1/saved-jobs").json()["items"] == []

    completed = execute_job_search_run(
        run_id,
        job_search_provider=provider,
        max_results=1,
    )

    assert len(completed.job_search_run.results) == 1
    run_payload = client.get(f"/api/v1/job-search-runs/{run_id}").json()
    assert "items" not in run_payload["job_search_run"]

    items_response = client.get(f"/api/v1/job-search-runs/{run_id}/items")
    assert items_response.status_code == 200
    payload = items_response.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 3
    assert sum(item["stage"] == "final" for item in payload["items"]) == 1
    assert sum(item["result"] is not None for item in payload["items"]) == 1
    assert client.get("/api/v1/saved-jobs").json()["items"] == []

    execute_job_search_run(
        run_id,
        job_search_provider=provider,
        max_results=1,
    )
    assert client.get(f"/api/v1/job-search-runs/{run_id}/items").json()["total"] == 3

    delete_response = client.delete(f"/api/v1/job-search-runs/{run_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/v1/job-search-runs/{run_id}/items").status_code == 404


def test_candidate_pool_remains_available_when_a_later_stage_fails(
    monkeypatch,
    tmp_path,
) -> None:
    confirmed = _create_session_with_confirmed_profile(
        tmp_path,
        monkeypatch,
        "job-search-live-items-partial.sqlite3",
    )
    provider = WideFakeProvider()
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=confirmed["profile_session"]["session_id"],
            search_mode="live_search",
            use_llm=False,
            max_results=1,
        ),
        job_search_provider=provider,
    )
    run_id = run_response.job_search_run.job_search_run_id
    monkeypatch.setattr(
        "app.application.job_search_usecases.filter_candidates",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("filter boom")),
    )

    failed = execute_job_search_run(
        run_id,
        job_search_provider=provider,
        max_results=1,
    )

    assert failed.job_search_run.status == "failed"
    items_response = client.get(f"/api/v1/job-search-runs/{run_id}/items")
    assert items_response.status_code == 200
    assert items_response.json()["total"] == 3
    assert all(item["stage"] == "recalled" for item in items_response.json()["items"])
