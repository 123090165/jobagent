from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from app.services.errors import JobAgentError
from app.services.search_providers.gemini_cli_provider import GeminiCLIProvider


def test_gemini_cli_provider_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_ENABLE_GEMINI_CLI", raising=False)

    provider = GeminiCLIProvider()
    with pytest.raises(JobAgentError, match="disabled") as exc_info:
        provider.search_jobs("python backend")

    assert exc_info.value.error_code == "search_provider_disabled"


def test_gemini_cli_provider_returns_search_result_set_from_valid_json(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "items": [
                        {
                            "title": "LLM Application Engineer",
                            "company": "Example Co",
                            "location": "Remote",
                            "url": "https://example.com/jobs/llm-app",
                            "snippet": "Build LLM application features and agent workflows.",
                            "source": "ignored",
                        }
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    provider = GeminiCLIProvider()
    result = provider.search_jobs("llm engineer", limit=5)

    assert result.provider == "gemini_cli"
    assert len(result.items) == 1
    assert result.items[0].source == "gemini_cli"
    assert "llm engineer" in captured["command"][-1].lower()
    assert captured["timeout"] == 20


def test_gemini_cli_provider_returns_timeout_error(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    provider = GeminiCLIProvider()
    with pytest.raises(JobAgentError, match="timed out") as exc_info:
        provider.search_jobs("ai agent")

    assert exc_info.value.error_code == "search_provider_timeout"


def test_gemini_cli_provider_returns_failed_error_for_nonzero_exit(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    provider = GeminiCLIProvider()
    with pytest.raises(JobAgentError, match="execution failed") as exc_info:
        provider.search_jobs("ai agent")

    assert exc_info.value.error_code == "search_provider_failed"


def test_gemini_cli_provider_rejects_non_json_output(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    provider = GeminiCLIProvider()
    with pytest.raises(JobAgentError, match="not valid JSON") as exc_info:
        provider.search_jobs("python backend")

    assert exc_info.value.error_code == "search_provider_output_invalid"


def test_gemini_cli_provider_filters_items_missing_title_or_snippet(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    def fake_run(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "items": [
                        {"title": "", "snippet": "missing title"},
                        {"title": "missing snippet", "snippet": ""},
                        {
                            "title": "AI Agent Developer",
                            "company": "Example Co",
                            "location": "Remote",
                            "url": "https://example.com/jobs/agent",
                            "snippet": "Build agent systems in Python.",
                        },
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    provider = GeminiCLIProvider()
    result = provider.search_jobs("agent", limit=5)

    assert len(result.items) == 1
    assert result.items[0].title == "AI Agent Developer"


def test_gemini_cli_provider_rejects_output_when_all_items_are_invalid(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    def fake_run(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"items": [{"title": "", "snippet": ""}]}),
            stderr="",
        )

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    provider = GeminiCLIProvider()
    with pytest.raises(JobAgentError, match="valid job items") as exc_info:
        provider.search_jobs("python backend")

    assert exc_info.value.error_code == "search_provider_output_invalid"
