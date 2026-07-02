from __future__ import annotations

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.application.job_search_usecases import create_job_search_run, execute_job_search_run
from app.main import app
from app.schemas.job_search import JobSearchRunCreateRequest
from app.services.job_search_providers.base import RawJobCandidate

client = TestClient(app)


class FakeProvider:
    provider_name = "mock"
    provider_kind = "mock"

    def search_jobs(self, *, query: str, location: str | None, limit: int):
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


class FakeJSONLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
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
        "app.application.job_search_usecases.resolve_llm_provider_for_switch",
        lambda *, use_deepseek: SimpleNamespace(
            provider="deepseek" if use_deepseek else "ollama",
            service=FakeJSONLLM(),
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
    assert completed.job_search_run.results[0].match_score == 89
    assert completed.job_search_run.results[0].score_breakdown["domain_alignment"] == 24
    assert completed.job_search_run.results[0].evidence_quotes
    assert completed.steps[-1].status == "completed"
    provider_step = next(step for step in completed.steps if step.name == "Provider search")
    assert provider_step.details["raw_candidate_count"] >= 2
    assert provider_step.details["deduped_candidate_count"] >= 2
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
    assert run_response.job_search_run.llm_enabled is False
