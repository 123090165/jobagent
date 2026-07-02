from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.application.resume_review_usecases import parse_resume_for_review
from app.main import app
from tests.fixtures.resumes.multidomain_flow_cases import (
    MULTIDOMAIN_FLOW_CASES,
    MultidomainFlowCase,
)

client = TestClient(app)


@pytest.mark.parametrize("case", MULTIDOMAIN_FLOW_CASES, ids=[case.case_id for case in MULTIDOMAIN_FLOW_CASES])
def test_multidomain_resume_reaches_truthful_search_preview(
    case: MultidomainFlowCase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / f"{case.case_id}.sqlite3"))
    resume_text = case.path.read_text(encoding="utf-8")

    session = client.post("/api/v1/profile-sessions").json()
    session_id = session["session_id"]
    client.post(f"/api/v1/profile-sessions/{session_id}/resume-text", json={"text": resume_text})
    review = parse_resume_for_review(session_id, llm_service=_DeterministicReviewLLM()).parsed_review

    draft_response = client.post(f"/api/v1/profile-sessions/{session_id}/profile-draft")
    assert draft_response.status_code == 200
    draft = draft_response.json()["profile_draft"]

    confirmed_response = client.post(f"/api/v1/profile-drafts/{draft['profile_draft_id']}/confirm")
    assert confirmed_response.status_code == 200
    confirmed = confirmed_response.json()["confirmed_profile"]

    preview_response = client.post(
        "/api/v1/job-search-runs/preview",
        json={
            "session_id": session_id,
            "search_mode": "local_mock",
            "max_results": 10,
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    intent = preview["search_intent"]

    _assert_any_terms_present(confirmed["target_roles"], case.expected_role_terms)
    _assert_any_terms_present(confirmed["target_directions"], case.expected_direction_terms)
    _assert_any_terms_present(
        intent["industry_domains"] + intent["evidence_skills"] + preview["provider_queries"],
        case.expected_intent_terms,
    )
    assert intent["role_titles"]
    assert preview["provider_queries"]
    assert preview["provider_queries"][0] == intent["broad_queries"][0]
    assert "Technical skill signal detected" not in review.target_signals
    assert "AI application signal" not in review.target_signals
    assert "data" not in [query.lower() for query in preview["provider_queries"]]
    assert "operations" not in [query.lower() for query in preview["provider_queries"]]

    combined_output = " ".join(
        confirmed["target_roles"]
        + confirmed["target_directions"]
        + confirmed["search_keywords"]
        + preview["provider_queries"]
        + intent["role_titles"]
        + intent["industry_domains"]
        + intent["evidence_skills"]
    ).lower()
    for forbidden in case.forbidden_terms:
        assert forbidden.lower() not in combined_output


def _assert_any_terms_present(values: list[str], expected_terms: tuple[str, ...]) -> None:
    combined = " ".join(values).lower()
    assert any(term.lower() in combined for term in expected_terms), (
        f"Expected one of {expected_terms!r} in {values!r}"
    )


class _DeterministicReviewLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        marker = "Non-authoritative deterministic candidate profile JSON:\n"
        start = user_prompt.index(marker) + len(marker)
        end = user_prompt.index("\n\nInstructions:", start)
        return {
            "resume_profile": json.loads(user_prompt[start:end]),
            "quality_warnings": [],
        }
