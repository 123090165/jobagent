from __future__ import annotations

import asyncio

from app.services.learning_resource_search import (
    DatabaseCatalogResourceSearch,
    OfficialCatalogResourceSearch,
    _resources_from_payloads,
    resource_error_summary,
    resolve_learning_resource_search,
)


def test_official_catalog_returns_only_matching_verified_resources() -> None:
    search = OfficialCatalogResourceSearch()

    linux = asyncio.run(search.search("Linux basic operations"))
    office = asyncio.run(search.search("Microsoft Office"))
    unknown = asyncio.run(search.search("unknown proprietary system"))

    assert linux[0].source == "Ubuntu Documentation"
    assert office[0].source == "Microsoft Support"
    assert unknown == []


def test_mcp_payload_parser_accepts_bounded_http_results() -> None:
    resources = _resources_from_payloads(
        "Linux",
        [{
            "results": [
                {"title": "Tutorial", "url": "https://example.com/tutorial", "snippet": "Useful"},
                {"title": "Unsafe", "url": "file:///tmp/local"},
                {"title": "Extra", "link": "https://example.org/extra"},
            ]
        }],
        limit=1,
    )

    assert len(resources) == 1
    assert resources[0].url == "https://example.com/tutorial"


def test_invalid_mcp_url_falls_back_to_catalog(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_LEARNING_MCP_URL", "file:///tmp/server")

    _search, mode = resolve_learning_resource_search()

    assert mode == "curated_catalog"


def test_database_catalog_uses_aliases_and_curated_priority(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "learning-catalog.sqlite3"))
    search = DatabaseCatalogResourceSearch()

    resources = asyncio.run(search.search("containerization with Docker", limit=2))

    assert resources
    assert resources[0].source == "Docker Documentation"


def test_database_catalog_covers_ppg_blood_pressure_without_remote_search(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "learning-catalog.sqlite3"))

    resources = asyncio.run(DatabaseCatalogResourceSearch().search(
        "Blood pressure estimation from PPG signals", limit=2
    ))

    assert len(resources) == 2
    assert all(item.source == "PhysioNet" for item in resources)


def test_nested_resource_error_is_unwrapped() -> None:
    error = ExceptionGroup("connection failed", [RuntimeError("mcp_server_unavailable")])

    assert resource_error_summary(error) == "RuntimeError: mcp_server_unavailable"
