from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ChatCitation
from app.services.chat_context_builder import ChatEvidence
from app.services.chat_personal_knowledge import PersonalKnowledgeSearchOutcome


client = TestClient(app)


def _register(username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password-123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class FakeChatLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str, expected_root_key=None):
        self.prompts.append(user_prompt)
        if "bounded career" in system_prompt:
            payload = json.loads(user_prompt)
            if payload.get("phase") == "choose_tools_or_answer":
                return {
                    "action": "use_tools",
                    "tool_calls": ["find_saved_jobs"],
                    "answer": "",
                    "citation_ids": [],
                    "limitations": [],
                }
            citation_ids = [
                item["citation_id"] for item in payload.get("evidence", [])
            ]
            return {
                "action": "final",
                "tool_calls": [],
                "answer": "The available evidence supports this career answer.",
                "citation_ids": citation_ids,
                "limitations": [],
            }
        if "Compress prior" in system_prompt:
            return {
                "user_goals": ["Compare saved jobs"],
                "preferences": [],
                "decisions": [],
                "unresolved_questions": [],
                "referenced_resource_ids": [],
            }
        return {
            "answer": "The saved Backend Engineer role is the strongest current option.",
            "citation_ids": [],
            "limitations": [],
        }


def _resolution(service) -> SimpleNamespace:
    return SimpleNamespace(provider="deepseek", service=service, configured=True)


def test_chat_agent_uses_mcp_personal_knowledge_with_grounded_citation(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "JOBAGENT_DB_PATH",
        str(tmp_path / "chat-personal-knowledge.sqlite3"),
    )
    headers = _register("chat-personal-knowledge")
    requested_queries: list[str] = []

    class PersonalKnowledgeAgent:
        def chat_completion_json(
            self,
            *,
            system_prompt,
            user_prompt,
            expected_root_key=None,
        ):
            payload = json.loads(user_prompt)
            if payload["phase"] == "choose_tools_or_answer":
                return {
                    "action": "use_tools",
                    "tool_calls": ["search_personal_knowledge"],
                    "answer": "",
                    "citation_ids": [],
                    "limitations": [],
                }
            assert payload["evidence"][0]["content"]["retrieval_source"] == (
                "modular_rag_mcp"
            )
            return {
                "action": "final",
                "tool_calls": [],
                "answer": "你收藏的 Platform Engineer 岗位明确要求 Kubernetes。",
                "citation_ids": ["saved_job:job-rag"],
                "limitations": [],
            }

    def fake_personal_search(question, **kwargs):
        requested_queries.append(question)
        return PersonalKnowledgeSearchOutcome(
            evidence=[
                ChatEvidence(
                    citation=ChatCitation(
                        citation_id="saved_job:job-rag",
                        source_type="saved_jobs",
                        resource_id="job-rag",
                        label="Platform Engineer · Example",
                        excerpt="Requires Kubernetes.",
                    ),
                    content={
                        "retrieval_source": "modular_rag_mcp",
                        "text": "Requires Kubernetes.",
                    },
                )
            ],
            sources=["saved_jobs"],
            warnings=[],
            service_available=True,
        )

    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: _resolution(PersonalKnowledgeAgent()),
    )
    monkeypatch.setattr(
        "app.services.chat_personal_knowledge.search_personal_knowledge",
        fake_personal_search,
    )
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={},
    ).json()

    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=headers,
        json={
            "client_turn_id": "rag-tool-turn",
            "question": "我收藏过哪些要求 Kubernetes 的岗位？",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert requested_queries == ["我收藏过哪些要求 Kubernetes 的岗位？"]
    assert payload["retrieval_used"] is True
    assert payload["retrieval_plan"]["requests"] == []
    assert payload["citations"][0]["resource_id"] == "job-rag"
    assert payload["answer"] == "你收藏的 Platform Engineer 岗位明确要求 Kubernetes。"


def test_chat_personal_knowledge_falls_back_when_mcp_is_not_configured(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "JOBAGENT_DB_PATH",
        str(tmp_path / "chat-personal-fallback.sqlite3"),
    )
    monkeypatch.delenv("JOBAGENT_RAG_MCP_URL", raising=False)
    headers = _register("chat-personal-fallback")
    job = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "Platform Engineer",
            "company": "Example",
            "raw_jd_text": "Build and operate Kubernetes platforms.",
        },
    ).json()
    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: SimpleNamespace(provider="mock", service=None),
    )
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={},
    ).json()

    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=headers,
        json={
            "client_turn_id": "rag-fallback-turn",
            "question": "我收藏过哪些要求 Kubernetes 的岗位？",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_used"] is True
    assert payload["retrieved_refs"] == [f"saved_job:{job['saved_job_id']}"]
    assert "personal_knowledge_unavailable:not_configured" in payload[
        "quality_warnings"
    ]
    assert "personal_knowledge_fallback:jobagent_database" in payload[
        "quality_warnings"
    ]


def test_browser_helper_session_is_scoped_to_chat(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "browser-helper-auth.sqlite3"))
    assert client.post("/api/v1/browser-helper/sessions").status_code == 401
    alice = _register("browser-helper-owner")
    bob = _register("browser-helper-other")
    alice_job = client.post(
        "/api/v1/saved-jobs",
        headers=alice,
        json={
            "title": "Selected backend role",
            "company": "Private company",
            "raw_jd_text": "Sensitive Python backend job description.",
            "notes": "Private application notes",
        },
    ).json()
    client.post(
        "/api/v1/saved-jobs",
        headers=bob,
        json={"title": "Other user role", "raw_jd_text": "Must stay isolated."},
    )
    bob_conversation = client.post(
        "/api/v1/chat/conversations", headers=bob, json={"title": "Private"}
    ).json()

    paired = client.post("/api/v1/browser-helper/sessions", headers=alice)
    assert paired.status_code == 201
    helper_headers = {"Authorization": f"Bearer {paired.json()['access_token']}"}

    assert client.get("/api/v1/auth/me", headers=helper_headers).status_code == 401
    assert client.get("/api/v1/saved-jobs", headers=helper_headers).status_code == 401
    catalog = client.get(
        "/api/v1/browser-helper/context-catalog", headers=helper_headers
    )
    assert catalog.status_code == 200
    assert catalog.json()["saved_jobs"] == [{
        "saved_job_id": alice_job["saved_job_id"],
        "title": "Selected backend role",
        "company": "Private company",
        "status": "saved",
    }]
    assert "raw_jd_text" not in catalog.text
    assert "Private application notes" not in catalog.text
    assert client.post(
        "/api/v1/chat/conversations", headers=helper_headers, json={"title": "From extension"}
    ).status_code == 201
    own = client.post(
        "/api/v1/chat/conversations", headers=helper_headers, json={"title": "Protected"}
    ).json()
    assert client.delete(
        f"/api/v1/chat/conversations/{own['conversation_id']}", headers=helper_headers
    ).status_code == 401
    assert client.get(
        f"/api/v1/chat/conversations/{bob_conversation['conversation_id']}/turns",
        headers=helper_headers,
    ).status_code == 404


def test_saved_job_turn_attachment_is_exact_and_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "saved-job-attachment.sqlite3"))
    alice = _register("saved-attachment-owner")
    bob = _register("saved-attachment-other")
    job = client.post(
        "/api/v1/saved-jobs",
        headers=alice,
        json={
            "title": "Exact saved role",
            "company": "Example",
            "raw_jd_text": "Build Python FastAPI services and reliable SQL APIs.",
        },
    ).json()
    bob_conversation = client.post(
        "/api/v1/chat/conversations", headers=bob, json={}
    ).json()
    foreign = client.post(
        f"/api/v1/chat/conversations/{bob_conversation['conversation_id']}/turns",
        headers=bob,
        json={
            "client_turn_id": "foreign-saved-job",
            "question": "Compare this role.",
            "context_attachments": [{
                "type": "saved_job",
                "saved_job_id": job["saved_job_id"],
            }],
        },
    )
    assert foreign.status_code == 404

    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: _resolution(FakeChatLLM()),
    )
    conversation = client.post(
        "/api/v1/chat/conversations", headers=alice, json={}
    ).json()
    turn = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=alice,
        json={
            "client_turn_id": "exact-saved-job",
            "question": "Compare this saved role with the current job.",
            "context_attachments": [{
                "type": "saved_job",
                "saved_job_id": job["saved_job_id"],
            }],
        },
    )
    assert turn.status_code == 200
    assert [(item["source"], item["strategy"]) for item in turn.json()["retrieval_plan"]["requests"]] == [
        ("saved_jobs", "use_attachment")
    ]
    assert turn.json()["retrieved_refs"] == [f"saved_job:{job['saved_job_id']}"]
    assert turn.json()["context_attachments"] == [{
        "type": "saved_job",
        "saved_job_id": job["saved_job_id"],
    }]

    retry = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=alice,
        json={
            "client_turn_id": "exact-saved-job-retry",
            "question": "This text must be ignored by an exact retry.",
            "retry_of_turn_id": turn.json()["turn_id"],
        },
    )
    assert retry.status_code == 200
    assert retry.json()["question"] == "Compare this saved role with the current job."
    assert retry.json()["retry_of_turn_id"] == turn.json()["turn_id"]
    assert retry.json()["context_attachments"] == turn.json()["context_attachments"]
    assert retry.json()["retrieved_refs"] == [f"saved_job:{job['saved_job_id']}"]

    foreign_retry = client.post(
        f"/api/v1/chat/conversations/{bob_conversation['conversation_id']}/turns",
        headers=bob,
        json={
            "client_turn_id": "foreign-retry",
            "question": "Retry another user's turn.",
            "retry_of_turn_id": turn.json()["turn_id"],
        },
    )
    assert foreign_retry.status_code == 404

    assert client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=alice,
        json={
            "client_turn_id": "invalid-retry-override",
            "question": "Retry with an override.",
            "retry_of_turn_id": turn.json()["turn_id"],
            "context_attachments": [{
                "type": "saved_job",
                "saved_job_id": job["saved_job_id"],
            }],
        },
    ).status_code == 422


def test_browser_capture_turn_attachment_is_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "capture-attachment-scope.sqlite3"))
    alice = _register("capture-owner")
    bob = _register("capture-other")
    jd_text = "Build Python FastAPI services, SQL APIs, integration tests, Docker workflows, and reliable production systems. " * 2
    capture = client.post(
        "/api/v1/browser/job-captures",
        headers=alice,
        json={
            "source": "company_site",
            "source_url": "https://jobs.example.com/role",
            "page_title": "Backend role",
            "title": "Backend role",
            "jd_text": jd_text,
            "captured_at": "2026-07-22T00:00:00+00:00",
            "extractor_version": "test",
        },
    ).json()
    conversation = client.post("/api/v1/chat/conversations", headers=bob, json={}).json()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=bob,
        json={
            "client_turn_id": "foreign-capture",
            "question": "Review this JD.",
            "context_attachments": [{
                "type": "browser_capture",
                "capture_id": capture["capture_id"],
            }],
        },
    )
    assert response.status_code == 404


def test_browser_capture_can_be_pinned_by_helper_without_copying_jd(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "capture-pin-scope.sqlite3"))
    alice = _register("capture-pin-owner")
    bob = _register("capture-pin-other")
    jd_text = "Build agent and RAG systems with Python, evaluation, APIs, and production monitoring. " * 2
    capture = client.post(
        "/api/v1/browser/job-captures",
        headers=alice,
        json={
            "source": "boss",
            "source_url": "https://www.zhipin.com/job_detail/example.html",
            "page_title": "Agent developer intern",
            "title": "Agent developer intern",
            "company": "Example AI",
            "jd_text": jd_text,
            "captured_at": "2026-07-22T00:00:00+00:00",
            "extractor_version": "test",
        },
    ).json()
    conversation = client.post(
        "/api/v1/chat/conversations", headers=alice, json={"title": "BOSS comparison"}
    ).json()
    paired = client.post("/api/v1/browser-helper/sessions", headers=alice).json()
    helper = {"Authorization": f"Bearer {paired['access_token']}"}

    attached = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/context/browser-captures",
        headers=helper,
        json={"type": "browser_capture", "capture_id": capture["capture_id"]},
    )

    assert attached.status_code == 200
    assert attached.json()["data_scope"]["browser_capture_ids"] == [capture["capture_id"]]
    assert jd_text not in attached.text
    memory = client.get(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/memory",
        headers=alice,
    ).json()
    assert memory["pinned_context"] == [{
        "source_type": "search_results",
        "resource_id": capture["capture_id"],
        "label": "Agent developer intern · Example AI",
        "status": "available",
    }]

    bob_conversation = client.post("/api/v1/chat/conversations", headers=bob, json={}).json()
    assert client.post(
        f"/api/v1/chat/conversations/{bob_conversation['conversation_id']}/context/browser-captures",
        headers=helper,
        json={"type": "browser_capture", "capture_id": capture["capture_id"]},
    ).status_code == 404


def test_agent_compares_previous_saved_job_with_pinned_browser_jd(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-agent-loop.sqlite3"))
    headers = _register("chat-agent-loop")
    saved_job = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "AI Health Algorithm Engineer",
            "company": "Example Health",
            "raw_jd_text": "Build physiological-signal models with Python and production evaluation.",
        },
    ).json()
    capture = client.post(
        "/api/v1/browser/job-captures",
        headers=headers,
        json={
            "source": "boss",
            "source_url": "https://www.zhipin.com/job_detail/agent-intern.html",
            "page_title": "LLM Developer Intern",
            "title": "LLM Developer Intern (Agent/RAG/Fine-tune)",
            "company": "Example AI",
            "jd_text": "Develop LLM agents, RAG pipelines, fine-tuning, evaluation, and Python services. " * 2,
            "captured_at": "2026-07-22T00:00:00+00:00",
            "extractor_version": "test",
        },
    ).json()

    class ComparisonAgent:
        def chat_completion_json(self, *, system_prompt, user_prompt, expected_root_key=None):
            payload = json.loads(user_prompt)
            if payload["phase"] == "choose_tools_or_answer":
                tools = (
                    ["find_saved_jobs"]
                    if "最高" in payload["question"]
                    else ["read_pinned_context", "read_previous_references", "read_profile"]
                )
                return {
                    "action": "use_tools",
                    "tool_calls": tools,
                    "answer": "",
                    "citation_ids": [],
                    "limitations": [],
                }
            citation_ids = [item["citation_id"] for item in payload["evidence"]]
            return {
                "action": "final",
                "tool_calls": [],
                "answer": "The comparison uses both the saved role and the pinned browser JD.",
                "citation_ids": citation_ids,
                "limitations": [],
            }

    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: _resolution(ComparisonAgent()),
    )
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={"data_scope": {"browser_capture_ids": [capture["capture_id"]]}},
    ).json()
    endpoint = f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns"
    first = client.post(
        endpoint,
        headers=headers,
        json={"client_turn_id": "highest-saved", "question": "找到我 saved job 里分数最高的 job"},
    )
    second = client.post(
        endpoint,
        headers=headers,
        json={"client_turn_id": "compare-two", "question": "对比一下这两个 job 对我的优劣"},
    )

    assert first.status_code == 200
    assert first.json()["citations"][0]["resource_id"] == saved_job["saved_job_id"]
    assert second.status_code == 200
    assert second.json()["analysis_mode"] == "llm"
    assert set(second.json()["retrieved_refs"]) == {
        f"saved_job:{saved_job['saved_job_id']}",
        f"search_result:browser_capture:{capture['capture_id']}",
    }
    assert {item["source_type"] for item in second.json()["citations"]} == {
        "saved_jobs",
        "search_results",
    }


def test_chat_turn_is_persisted_grounded_and_idempotent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat.sqlite3"))
    headers = _register("chat-alice")
    job = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "Example",
            "raw_jd_text": "Build Python and FastAPI services.",
        },
    ).json()
    fake = FakeChatLLM()

    def fake_resolve(provider=None):
        service = fake
        original = service.chat_completion_json

        def completion(*, system_prompt, user_prompt, expected_root_key=None):
            if "bounded career" in system_prompt:
                service.prompts.append(user_prompt)
                return {
                    "answer": "The saved Backend Engineer role is the strongest current option.",
                    "citation_ids": [f"saved_job:{job['saved_job_id']}"],
                    "limitations": [],
                }
            return original(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                expected_root_key=expected_root_key,
            )

        return _resolution(SimpleNamespace(chat_completion_json=completion))

    monkeypatch.setattr("app.application.chat_usecases.resolve_llm_provider", fake_resolve)
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={"data_scope": {"saved_job_ids": [job["saved_job_id"]]}},
    )
    assert conversation.status_code == 201
    conversation_id = conversation.json()["conversation_id"]
    payload = {"client_turn_id": "turn-1", "question": "我收藏的岗位怎么样？"}

    first = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=headers,
        json=payload,
    )
    second = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 200
    assert first.json()["status"] == "completed"
    assert first.json()["retrieval_used"] is True
    assert first.json()["retrieval_plan"]["agent_sources"] == ["saved_jobs"]
    assert first.json()["retrieval_plan"]["requests"][0]["strategy"] == "use_pinned"
    assert first.json()["citations"][0]["resource_id"] == job["saved_job_id"]
    assert second.json()["turn_id"] == first.json()["turn_id"]
    history = client.get(
        f"/api/v1/chat/conversations/{conversation_id}/turns", headers=headers
    ).json()["items"]
    assert len(history) == 1
    assert job["raw_jd_text"] in "\n".join(fake.prompts)


def test_chat_memory_and_conversation_are_user_scoped_and_deletable(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "chat-delete.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(db_path))
    alice = _register("chat-owner")
    bob = _register("chat-other")
    conversation = client.post(
        "/api/v1/chat/conversations", headers=alice, json={"data_access_mode": "off"}
    ).json()
    conversation_id = conversation["conversation_id"]

    other = client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=bob)
    assert other.status_code == 404
    turn = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=alice,
        json={"client_turn_id": "private-1", "question": "How should I prepare for an interview?"},
    )
    assert turn.status_code == 200

    assert client.delete(
        f"/api/v1/chat/conversations/{conversation_id}/memory", headers=bob
    ).status_code == 404
    assert client.delete(
        f"/api/v1/chat/conversations/{conversation_id}/memory", headers=alice
    ).status_code == 204
    assert client.get(
        f"/api/v1/chat/conversations/{conversation_id}/turns", headers=alice
    ).json()["items"] == []

    assert client.delete(
        f"/api/v1/chat/conversations/{conversation_id}", headers=alice
    ).status_code == 204
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM chat_conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM chat_turns WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0] == 0


def test_foreign_context_resource_is_rejected_before_chat_creation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-scope.sqlite3"))
    alice = _register("chat-scope-owner")
    bob = _register("chat-scope-other")
    job = client.post(
        "/api/v1/saved-jobs",
        headers=alice,
        json={"title": "Private role", "raw_jd_text": "Private JD evidence."},
    ).json()

    response = client.post(
        "/api/v1/chat/conversations",
        headers=bob,
        json={"data_scope": {"saved_job_ids": [job["saved_job_id"]]}},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "chat_context_resource_not_found"


def test_deleting_turn_keeps_sequences_monotonic_and_removes_auto_title(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-turn-delete.sqlite3"))
    headers = _register("chat-turn-delete")
    conversation = client.post(
        "/api/v1/chat/conversations", headers=headers, json={"data_access_mode": "off"}
    ).json()
    conversation_id = conversation["conversation_id"]

    first = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=headers,
        json={"client_turn_id": "turn-a", "question": "How should I prepare for an interview?"},
    ).json()
    second = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=headers,
        json={"client_turn_id": "turn-b", "question": "What should I practice next?"},
    ).json()
    assert (first["sequence"], second["sequence"]) == (1, 2)

    assert client.delete(
        f"/api/v1/chat/conversations/{conversation_id}/turns/{first['turn_id']}",
        headers=headers,
    ).status_code == 204
    updated = client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=headers
    ).json()
    assert updated["title"] == "What should I practice next?"

    third = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=headers,
        json={"client_turn_id": "turn-c", "question": "How do I structure the answer?"},
    ).json()
    assert third["sequence"] == 3


def test_ordinary_out_of_scope_question_does_not_retrieve_or_refuse(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-refuse.sqlite3"))
    headers = _register("chat-refuse")
    conversation = client.post(
        "/api/v1/chat/conversations", headers=headers, json={"data_access_mode": "always"}
    ).json()

    def unexpected_retrieval(*args, **kwargs):
        raise AssertionError("business context retrieval must not run")

    monkeypatch.setattr(
        "app.application.chat_usecases.build_chat_evidence_with_personal_knowledge",
        unexpected_retrieval,
    )
    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: SimpleNamespace(provider="mock", service=None),
    )
    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=headers,
        json={"client_turn_id": "out-of-scope", "question": "What is today's weather?"},
    )

    assert response.status_code == 200
    assert response.json()["analysis_mode"] == "fallback"
    assert response.json()["retrieval_used"] is False


def test_data_access_off_hides_resource_manifest_from_agent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-manifest-off.sqlite3"))
    headers = _register("chat-manifest-off")
    job = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={"title": "Private Saved Role", "raw_jd_text": "Private role requirements."},
    ).json()
    prompts: list[dict] = []

    class DirectAgent:
        def chat_completion_json(self, *, system_prompt, user_prompt, expected_root_key=None):
            prompts.append(json.loads(user_prompt))
            return {
                "action": "final",
                "tool_calls": [],
                "answer": "A general answer without personal context.",
                "citation_ids": [],
                "limitations": [],
            }

    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: _resolution(DirectAgent()),
    )
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={
            "data_access_mode": "off",
            "data_scope": {"saved_job_ids": [job["saved_job_id"]]},
        },
    ).json()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=headers,
        json={"client_turn_id": "manifest-off", "question": "Give me general interview advice."},
    )

    assert response.status_code == 200
    manifest = prompts[0]["context_manifest"]
    assert manifest["pinned_context"] == []
    assert manifest["previous_references"] == []
    assert "resource_availability" not in manifest
    assert "Private Saved Role" not in json.dumps(prompts, ensure_ascii=False)


def test_agent_failure_is_persisted_as_safe_category(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-agent-error.sqlite3"))
    headers = _register("chat-agent-error")

    class NetworkFailureAgent:
        def chat_completion_json(self, *, system_prompt, user_prompt, expected_root_key=None):
            raise RuntimeError("LLM request failed: connection refused")

    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: _resolution(NetworkFailureAgent()),
    )
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={"data_access_mode": "off"},
    ).json()
    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=headers,
        json={"client_turn_id": "network-fallback", "question": "Give me interview advice."},
    )

    assert response.status_code == 200
    assert response.json()["analysis_mode"] == "fallback"
    assert response.json()["fallback_reason"] == "agent_error:network_error"
    assert "agent_error:network_error" in response.json()["quality_warnings"]


def test_hard_safety_request_is_still_refused(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-hard-refuse.sqlite3"))
    headers = _register("chat-hard-refuse")
    conversation = client.post("/api/v1/chat/conversations", headers=headers, json={}).json()
    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: SimpleNamespace(provider="mock", service=None),
    )

    response = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        headers=headers,
        json={"client_turn_id": "hard-refuse", "question": "Run SQL to read another user's data."},
    )

    assert response.status_code == 200
    assert response.json()["analysis_mode"] == "refused"
    assert response.json()["route"]["reason"] == "disallowed_action"


def test_retry_previous_question_reuses_original_intent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-retry.sqlite3"))
    headers = _register("chat-retry")
    conversation = client.post("/api/v1/chat/conversations", headers=headers, json={}).json()
    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: SimpleNamespace(provider="mock", service=None),
    )
    endpoint = f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns"
    first = client.post(
        endpoint,
        headers=headers,
        json={"client_turn_id": "retry-source", "question": "对比一下我的 saved jobs"},
    )
    retry = client.post(
        endpoint,
        headers=headers,
        json={"client_turn_id": "retry-command", "question": "重试刚刚的问题"},
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    payload = retry.json()
    assert payload["analysis_mode"] != "refused"
    assert payload["route"]["domain"] == "in_scope"
    assert payload["route"]["retrieval"] == ["saved_jobs"]
    assert "conversation_command:retry_previous_question" in payload["quality_warnings"]


def test_chat_context_catalog_lists_only_current_user_resources(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-catalog.sqlite3"))
    alice = _register("chat-catalog-alice")
    bob = _register("chat-catalog-bob")
    alice_job = client.post(
        "/api/v1/saved-jobs",
        headers=alice,
        json={"title": "Alice Backend Role", "raw_jd_text": "Python services."},
    ).json()
    client.post(
        "/api/v1/saved-jobs",
        headers=bob,
        json={"title": "Bob Private Role", "raw_jd_text": "Private requirements."},
    )

    response = client.get("/api/v1/chat/context-catalog", headers=alice)

    assert response.status_code == 200
    assert [item["saved_job_id"] for item in response.json()["saved_jobs"]] == [
        alice_job["saved_job_id"]
    ]
    assert "Bob Private Role" not in str(response.json())


def test_chat_memory_status_is_derived_and_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "chat-memory-status.sqlite3"))
    alice = _register("chat-memory-alice")
    bob = _register("chat-memory-bob")
    job = client.post(
        "/api/v1/saved-jobs",
        headers=alice,
        json={"title": "Platform Engineer", "company": "Example", "raw_jd_text": "Python."},
    ).json()
    monkeypatch.setattr(
        "app.application.chat_usecases.resolve_llm_provider",
        lambda provider=None: _resolution(None),
    )
    conversation = client.post(
        "/api/v1/chat/conversations",
        headers=alice,
        json={"data_scope": {"saved_job_ids": [job["saved_job_id"]]}},
    ).json()
    conversation_id = conversation["conversation_id"]
    turn = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/turns",
        headers=alice,
        json={"client_turn_id": "memory-turn", "question": "What about this saved job?"},
    )
    assert turn.status_code == 200

    response = client.get(
        f"/api/v1/chat/conversations/{conversation_id}/memory",
        headers=alice,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_turn_count"] == 1
    assert payload["recent_turn_count"] == 1
    assert payload["summary"] == {}
    assert payload["pinned_context"] == [{
        "source_type": "saved_jobs",
        "resource_id": job["saved_job_id"],
        "label": "Platform Engineer · Example",
        "status": "available",
    }]
    assert payload["previous_references"][0]["resource_id"] == job["saved_job_id"]
    assert client.get(
        f"/api/v1/chat/conversations/{conversation_id}/memory",
        headers=bob,
    ).status_code == 404
