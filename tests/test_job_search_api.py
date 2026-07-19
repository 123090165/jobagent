from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_session_with_confirmed_profile(
    tmp_path,
    monkeypatch,
    name: str = "job-search.sqlite3",
) -> dict:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / name))
    session = client.post("/api/v1/profile-sessions").json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={
            "text": (
                "Name: Jane Doe\n"
                "Role: Backend Engineer\n"
                "Skills: Python, FastAPI, SQL, LangGraph, Docker\n"
                "Project: Built JobAgent resume review flow with pytest coverage.\n"
            )
        },
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume")
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft"
    ).json()
    confirmed = client.post(
        f"/api/v1/profile-drafts/{draft['profile_draft']['profile_draft_id']}/confirm"
    ).json()
    return confirmed


def _get_run_payload(run_id: str) -> dict:
    response = client.get(f"/api/v1/job-search-runs/{run_id}")
    assert response.status_code == 200
    return response.json()


def test_job_search_requires_existing_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-missing-session.sqlite3"))

    response = client.post("/api/v1/job-search-runs", json={"session_id": "missing"})

    assert response.status_code == 404
    assert response.json()["error_code"] == "profile_session_not_found"


def test_job_search_requires_confirmed_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-no-confirmed.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post("/api/v1/job-search-runs", json={"session_id": session["session_id"]})

    assert response.status_code == 409
    assert response.json()["error_code"] == "confirmed_profile_required"


def test_job_search_preview_requires_confirmed_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-preview-no-confirmed.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post("/api/v1/job-search-runs/preview", json={"session_id": session["session_id"]})

    assert response.status_code == 409
    assert response.json()["error_code"] == "confirmed_profile_required"


def test_job_search_preview_returns_plan_without_creating_run(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-preview.sqlite3")
    session_id = confirmed["profile_session"]["session_id"]

    response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "local_mock",
            "target_roles": ["健康算法实习生"],
            "keywords": ["生理信号处理", "PPG", "ECG"],
            "locations": ["深圳"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmed_profile_id"] == confirmed["confirmed_profile"]["confirmed_profile_id"]
    assert payload["planning_mode"] == "deterministic"
    assert payload["query"] == "健康算法实习生"
    assert payload["provider_queries"][0].startswith("健康算法实习生")
    assert "健康算法实习生 生理信号处理 PPG" in payload["provider_queries"]
    assert payload["locations"] == ["深圳"]
    assert "PPG" in payload["search_signal_terms"]
    assert "ECG" in payload["search_signal_terms"]
    assert payload["provider_query_count"] == 0
    assert payload["estimated_provider_requests"] == 0
    assert payload["estimated_total_llm_requests"] == 0
    assert payload["search_intent"]["role_titles"]
    assert "generic_tools" in payload["search_intent"]
    assert payload["search_source_kind"] == "mock"
    assert payload["recall_queries"]
    assert payload["ranking_signals"]
    assert "Local mock search" in " ".join(payload["query_strategy_notes"])

    runs = client.get(f"/api/v1/profile-sessions/{session_id}/job-search-runs")
    assert runs.status_code == 200
    assert runs.json()["items"] == []


def test_job_search_preview_returns_cuhksz_search_urls(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-preview-cuhksz.sqlite3")
    session_id = confirmed["profile_session"]["session_id"]

    response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "live_search",
            "search_provider": "cuhksz_career",
            "target_roles": ["健康算法实习生"],
            "keywords": ["PPG", "ECG"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_search_terms"][:4] == ["算法", "健康算法", "PPG", "ECG"]
    assert "健康算法实习生" not in payload["provider_search_terms"]
    assert any("title=%E7%AE%97%E6%B3%95" in url for url in payload["provider_search_urls"])
    assert any("title=%E5%81%A5%E5%BA%B7%E7%AE%97%E6%B3%95" in url for url in payload["provider_search_urls"])
    assert 1 <= payload["provider_query_count"] <= 6
    assert payload["estimated_provider_requests"] >= len(payload["provider_search_urls"])
    assert payload["estimated_candidate_pool_size"] <= 60
    assert payload["estimated_total_llm_requests"] == (
        payload["estimated_llm_planning_requests"]
        + payload["estimated_llm_filtering_requests"]
        + payload["estimated_llm_analysis_requests"]
    )
    assert any("CUHKSZ" in note for note in payload["query_strategy_notes"])
    assert payload["search_intent"]["mode"] in {"deterministic", "llm", "fallback"}
    assert "industry_domains" in payload["search_intent"]
    assert payload["search_source_kind"] == "native_job_board"
    assert payload["recall_queries"]
    assert payload["ranking_signals"]


def test_job_search_preview_separates_analysis_mode_from_provider(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-preview-llm-config.sqlite3")
    session_id = confirmed["profile_session"]["session_id"]

    deterministic_response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "live_search",
            "search_provider": "cuhksz_career",
            "analysis_mode": "deterministic",
            "llm_provider": "deepseek",
        },
    )
    llm_response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "live_search",
            "search_provider": "cuhksz_career",
            "analysis_mode": "llm",
            "llm_provider": "deepseek",
        },
    )

    assert deterministic_response.status_code == 200
    deterministic_payload = deterministic_response.json()
    assert deterministic_payload["analysis_mode"] == "deterministic"
    assert deterministic_payload["llm_enabled"] is False
    assert deterministic_payload["llm_provider"] is None
    assert deterministic_payload["estimated_total_llm_requests"] == 0

    assert llm_response.status_code == 200
    llm_payload = llm_response.json()
    assert llm_payload["analysis_mode"] == "llm"
    assert llm_payload["llm_enabled"] is True
    assert llm_payload["llm_provider"] == "deepseek"
    assert llm_payload["estimated_total_llm_requests"] > 0


def test_job_search_preview_returns_web_search_source_strategy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_WEB_SEARCH_SITES", "career.example.com")
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-preview-web.sqlite3")
    session_id = confirmed["profile_session"]["session_id"]

    response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "live_search",
            "search_provider": "serper_web",
            "target_roles": ["Brand Marketing Intern"],
            "keywords": ["market research", "consumer insight", "Excel"],
            "locations": ["Shanghai"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_provider"] == "serper_web"
    assert payload["search_source_kind"] == "search_engine"
    assert payload["provider_search_terms"]
    assert any("site%3Acareer.example.com" in url for url in payload["provider_search_urls"])
    assert any("Search engine" in note or "search-engine" in note for note in payload["query_strategy_notes"])


def test_job_search_preview_returns_selected_multi_source_strategy(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(
        tmp_path,
        monkeypatch,
        "job-search-preview-multi-source.sqlite3",
    )
    session_id = confirmed["profile_session"]["session_id"]

    response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "live_search",
            "search_provider": "multi_source",
            "selected_sources": ["cuhksz_career", "linkedin", "remoteok"],
            "target_roles": ["Brand Marketing Intern"],
            "keywords": ["market research", "consumer insight"],
            "locations": ["Shanghai"],
            "max_results": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_provider"] == "multi_source:cuhksz_career,linkedin,remoteok"
    assert payload["selected_sources"] == ["cuhksz_career", "linkedin", "remoteok"]
    assert payload["search_source_kind"] == "hybrid"
    assert any("Selected sources" in note for note in payload["search_source_notes"])
    assert any("career.cuhk.edu.cn" in url for url in payload["provider_search_urls"])
    assert any("site%3Alinkedin.com%2Fjobs" in url for url in payload["provider_search_urls"])
    assert any("remoteok.com/api" in url for url in payload["provider_search_urls"])
    assert any("Multi-source search" in note for note in payload["query_strategy_notes"])
    assert payload["estimated_candidate_pool_size"] <= 60


def test_browser_helper_job_search_requires_candidates(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-browser-empty.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs/browser-helper",
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "query": "browser helper demo",
            "platforms": ["demo"],
            "candidates": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "browser_helper_candidates_required"


def test_browser_helper_job_search_accepts_payload_candidates(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-browser.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs/browser-helper",
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "query": "Backend Engineer",
            "helper_version": "0.1.0",
            "platforms": ["demo"],
            "max_results": 5,
            "candidates": [
                {
                    "title": "Backend Engineer Intern",
                    "company": "Browser Helper Demo",
                    "location": "Remote",
                    "source_url": "https://jobs.example.com/browser-helper/backend",
                    "source_provider": "browser_helper_demo",
                    "snippet": "Python FastAPI SQL APIs and backend platform work.",
                    "raw_description": "Python FastAPI SQL APIs and backend platform work.",
                    "detail_status": "browser_helper_payload",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run = payload["job_search_run"]
    assert run["status"] == "running"
    assert run["search_mode"] == "browser_helper"
    assert run["search_provider"] == "browser_helper:demo"
    assert run["results"] == []
    completed_payload = _get_run_payload(run["job_search_run_id"])
    run = completed_payload["job_search_run"]
    assert run["status"] == "completed"
    assert run["results"]
    assert run["results"][0]["source_provider"] == "browser_helper_demo"
    assert run["results"][0]["source_url"] == "https://jobs.example.com/browser-helper/backend"
    provider_step = next(step for step in completed_payload["steps"] if step["name"] == "Provider search")
    assert provider_step["details"]["source_candidate_counts"]["browser_helper_demo"] == 1


def test_browser_helper_job_search_combines_selected_sources(monkeypatch, tmp_path) -> None:
    from app.application import job_search_usecases
    from app.services.job_search_providers.base import RawJobCandidate

    class FakeSelectedProvider:
        provider_kind = "native_api"
        detail_strategy = "fake_test_provider"

        def __init__(self, source_name: str) -> None:
            self.provider_name = source_name
            self.source_names = [source_name]

        def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
            return [
                RawJobCandidate(
                    title=f"{self.provider_name} Backend Engineer",
                    company=f"{self.provider_name} Test Company",
                    location=location or "Remote",
                    source_url=f"https://jobs.example.com/{self.provider_name}/{query.replace(' ', '-').lower()}",
                    source_provider=self.provider_name,
                    snippet="Python FastAPI SQL backend APIs and platform work.",
                    raw_description="Python FastAPI SQL backend APIs and platform work.",
                    detail_status="test_provider_payload",
                )
            ][:limit]

    monkeypatch.setattr(
        job_search_usecases,
        "resolve_job_search_provider",
        lambda source_name: FakeSelectedProvider(source_name),
    )
    confirmed = _create_session_with_confirmed_profile(
        tmp_path,
        monkeypatch,
        "job-search-browser-selected-sources.sqlite3",
    )

    response = client.post(
        "/api/v1/job-search-runs/browser-helper",
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "query": "Backend Engineer",
            "helper_version": "0.2.0",
            "platforms": ["boss"],
            "selected_sources": ["cuhksz_career", "remoteok"],
            "max_results": 10,
            "candidates": [
                {
                    "title": "BOSS Backend Engineer",
                    "company": "BOSS Test Company",
                    "location": "Shenzhen",
                    "source_url": "https://www.zhipin.com/job_detail/test.html",
                    "source_provider": "boss_zhipin",
                    "snippet": "Python FastAPI SQL APIs and backend platform work.",
                    "raw_description": "Python FastAPI SQL APIs and backend platform work.",
                    "detail_status": "boss_search_list_dom",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run = payload["job_search_run"]
    assert run["status"] == "running"
    assert run["search_provider"] == "browser_helper:boss,cuhksz_career,remoteok"
    assert run["selected_sources"] == ["cuhksz_career", "remoteok"]
    assert run["results"] == []
    completed_payload = _get_run_payload(run["job_search_run_id"])
    run = completed_payload["job_search_run"]
    assert run["status"] == "completed"
    source_providers = {item["source_provider"] for item in run["results"]}
    assert "boss_zhipin" in source_providers
    assert "cuhksz_career" in source_providers
    assert "remoteok" in source_providers
    provider_step = next(step for step in completed_payload["steps"] if step["name"] == "Provider search")
    details = provider_step["details"]
    assert details["provider"] == "browser_helper:boss,cuhksz_career,remoteok"
    assert details["source_kind"] == "hybrid"
    assert details["selected_sources"] == ["cuhksz_career", "remoteok"]
    assert details["source_candidate_counts"]["boss_zhipin"] == 1
    assert details["source_candidate_counts"]["cuhksz_career"] >= 1
    assert details["source_candidate_counts"]["remoteok"] >= 1
    assert details["logical_provider_call_count"] >= 3
    source_attempts = details["source_attempts"]
    assert any(item["source"] == "browser_helper:boss" and item["returned_count"] >= 1 for item in source_attempts)
    assert any(item["source"] == "cuhksz_career" and item["returned_count"] >= 1 for item in source_attempts)
    assert any(item["source"] == "remoteok" and item["returned_count"] >= 1 for item in source_attempts)


def test_browser_helper_empty_candidates_still_runs_selected_sources(monkeypatch, tmp_path) -> None:
    from app.application import job_search_usecases
    from app.services.job_search_providers.base import RawJobCandidate

    class FakeSelectedProvider:
        provider_kind = "native_job_board"
        detail_strategy = "fake_selected_provider"

        def __init__(self, source_name: str) -> None:
            self.provider_name = source_name
            self.source_names = [source_name]

        def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
            return [
                RawJobCandidate(
                    title=f"{self.provider_name} Algorithm Intern",
                    company=f"{self.provider_name} Test Company",
                    location=location or "Shenzhen",
                    source_url=f"https://jobs.example.com/{self.provider_name}/algorithm-intern",
                    source_provider=self.provider_name,
                    snippet="Python machine learning algorithm internship with signal processing work.",
                    raw_description="Python machine learning algorithm internship with signal processing work.",
                    detail_status="test_provider_payload",
                )
            ][:limit]

    monkeypatch.setattr(
        job_search_usecases,
        "resolve_job_search_provider",
        lambda source_name: FakeSelectedProvider(source_name),
    )
    confirmed = _create_session_with_confirmed_profile(
        tmp_path,
        monkeypatch,
        "job-search-browser-empty-selected-sources.sqlite3",
    )

    response = client.post(
        "/api/v1/job-search-runs/browser-helper",
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "query": "Algorithm Intern",
            "helper_version": "0.2.0",
            "platforms": ["boss"],
            "selected_sources": ["cuhksz_career"],
            "max_results": 10,
            "candidates": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run = payload["job_search_run"]
    assert run["status"] == "running"
    assert run["search_provider"] == "browser_helper:boss,cuhksz_career"
    assert run["selected_sources"] == ["cuhksz_career"]
    assert run["results"] == []
    completed_payload = _get_run_payload(run["job_search_run_id"])
    run = completed_payload["job_search_run"]
    assert run["status"] == "completed"
    source_providers = {item["source_provider"] for item in run["results"]}
    assert "cuhksz_career" in source_providers
    assert "boss_zhipin" not in source_providers
    provider_step = next(step for step in completed_payload["steps"] if step["name"] == "Provider search")
    details = provider_step["details"]
    assert details["source_candidate_counts"]["cuhksz_career"] >= 1
    source_attempts = details["source_attempts"]
    assert any(item["source"] == "browser_helper:boss" and item["returned_count"] == 0 for item in source_attempts)
    assert any(item["source"] == "cuhksz_career" and item["returned_count"] >= 1 for item in source_attempts)


def test_job_search_creates_run_and_updates_session(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-create.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"], "search_mode": "local_mock"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_search_run"]["job_search_run_id"]
    assert payload["profile_session"]["current_step"] == "job_search_completed"
    assert len(payload["job_search_run"]["results"]) >= 5


def test_job_search_uses_local_mock_source(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-source.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"], "search_mode": "local_mock"},
    )

    results = response.json()["job_search_run"]["results"]
    assert all(item["source"] == "local_mock" for item in results)


def test_job_search_results_have_expected_fields(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-fields.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"], "search_mode": "local_mock"},
    )

    first = response.json()["job_search_run"]["results"][0]
    assert first["title"]
    assert first["company"]
    assert first["location"]
    assert isinstance(first["match_score"], int)
    assert isinstance(first["match_reasons"], list)


def test_get_job_search_run_returns_run(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-get.sqlite3")
    created = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"], "search_mode": "local_mock"},
    ).json()

    response = client.get(f"/api/v1/job-search-runs/{created['job_search_run']['job_search_run_id']}")

    assert response.status_code == 200
    assert (
        response.json()["job_search_run"]["job_search_run_id"]
        == created["job_search_run"]["job_search_run_id"]
    )


def test_get_missing_job_search_run_returns_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-missing-run.sqlite3"))

    response = client.get("/api/v1/job-search-runs/missing-run")

    assert response.status_code == 404
    assert response.json()["error_code"] == "job_search_run_not_found"


def test_list_job_search_runs_by_session_returns_runs(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-list.sqlite3")
    session_id = confirmed["profile_session"]["session_id"]
    client.post("/api/v1/job-search-runs", json={"session_id": session_id, "search_mode": "local_mock"})
    response = client.get(f"/api/v1/profile-sessions/{session_id}/job-search-runs")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_job_search_does_not_require_network_or_llm(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-local-only.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"], "search_mode": "local_mock"},
    )

    assert response.status_code == 200
    assert response.json()["job_search_run"]["status"] == "completed"
