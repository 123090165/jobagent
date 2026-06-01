from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.schemas.search import SearchResultItem, SearchResultSet
from app.services.errors import JobAgentError
from app.services.search_providers.base import SearchProvider

DEFAULT_GEMINI_CLI_COMMAND = "gemini"
DEFAULT_GEMINI_CLI_TIMEOUT_SECONDS = 20

GEMINI_CLI_PROMPT_TEMPLATE = """Search for public job postings related to this query: {query}

Return JSON only with this exact shape:
{{
  "items": [
    {{
      "title": "...",
      "company": "...",
      "location": "...",
      "url": "...",
      "snippet": "...",
      "source": "gemini_cli"
    }}
  ]
}}

Do not return markdown.
Do not return explanation text.
Do not include any fields outside this JSON object.
"""


class GeminiCLIProvider(SearchProvider):
    name = "gemini_cli"

    def search_jobs(self, query: str, limit: int = 5) -> SearchResultSet:
        if not is_gemini_cli_enabled():
            raise JobAgentError(
                "Gemini CLI search provider is disabled",
                "search_provider_disabled",
            )

        prompt = GEMINI_CLI_PROMPT_TEMPLATE.format(query=query)
        command = [*get_gemini_cli_command_parts(), prompt]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=get_gemini_cli_timeout_seconds(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise JobAgentError(
                "Search provider timed out",
                "search_provider_timeout",
            ) from exc
        except OSError as exc:
            raise JobAgentError(
                "Search provider execution failed",
                "search_provider_failed",
            ) from exc

        if completed.returncode != 0:
            raise JobAgentError(
                "Search provider execution failed",
                "search_provider_failed",
            )

        items = _parse_gemini_cli_items(completed.stdout, limit=limit)
        return SearchResultSet(
            query=query,
            provider=self.name,
            items=items,
        )


def is_gemini_cli_enabled() -> bool:
    return os.getenv("JOBAGENT_ENABLE_GEMINI_CLI", "0") == "1"


def get_gemini_cli_command_parts() -> list[str]:
    raw_command = os.getenv("JOBAGENT_GEMINI_CLI_COMMAND", DEFAULT_GEMINI_CLI_COMMAND).strip()
    if not raw_command:
        return [DEFAULT_GEMINI_CLI_COMMAND]

    try:
        parts = shlex.split(raw_command, posix=False)
    except ValueError:
        parts = [raw_command]
    return parts or [DEFAULT_GEMINI_CLI_COMMAND]


def get_gemini_cli_timeout_seconds() -> int:
    raw_value = os.getenv(
        "JOBAGENT_GEMINI_CLI_TIMEOUT_SECONDS",
        str(DEFAULT_GEMINI_CLI_TIMEOUT_SECONDS),
    ).strip()
    try:
        timeout = int(raw_value)
    except ValueError:
        return DEFAULT_GEMINI_CLI_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_GEMINI_CLI_TIMEOUT_SECONDS


def _parse_gemini_cli_items(raw_output: str, *, limit: int) -> list[SearchResultItem]:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise JobAgentError(
            "Search provider output is not valid JSON",
            "search_provider_output_invalid",
        ) from exc

    if not isinstance(payload, dict):
        raise JobAgentError(
            "Search provider output must be a JSON object",
            "search_provider_output_invalid",
        )

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise JobAgentError(
            "Search provider output must include an items list",
            "search_provider_output_invalid",
        )

    retrieved_at = datetime.now(timezone.utc)
    parsed_items: list[SearchResultItem] = []
    for raw_item in raw_items:
        normalized = _normalize_item(raw_item)
        if normalized is None:
            continue
        parsed_items.append(
            SearchResultItem(
                title=normalized["title"],
                company=normalized["company"],
                location=normalized["location"],
                url=normalized["url"],
                snippet=normalized["snippet"],
                source="gemini_cli",
                retrieved_at=retrieved_at,
            )
        )
        if len(parsed_items) >= limit:
            break

    if not parsed_items:
        raise JobAgentError(
            "Search provider output did not include any valid job items",
            "search_provider_output_invalid",
        )

    return parsed_items


def _normalize_item(raw_item: Any) -> dict[str, str] | None:
    if not isinstance(raw_item, dict):
        return None

    title = str(raw_item.get("title", "")).strip()
    snippet = str(raw_item.get("snippet", "")).strip()
    if not title or not snippet:
        return None

    return {
        "title": title,
        "company": str(raw_item.get("company", "")).strip(),
        "location": str(raw_item.get("location", "")).strip(),
        "url": str(raw_item.get("url", "")).strip(),
        "snippet": snippet,
    }
