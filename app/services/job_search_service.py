from __future__ import annotations

from app.schemas.search import SearchResultSet
from app.services.errors import JobAgentError
from app.services.search_providers import GeminiCLIProvider, MockSearchProvider, SearchProvider

MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 20

_PROVIDERS: dict[str, SearchProvider] = {
    "gemini_cli": GeminiCLIProvider(),
    "mock": MockSearchProvider(),
}


def search_jobs(query: str, provider: str = "mock", limit: int = 5) -> SearchResultSet:
    normalized_query = query.strip()
    if not normalized_query:
        raise JobAgentError("Search query cannot be empty", "search_query_invalid")

    if limit < MIN_SEARCH_LIMIT or limit > MAX_SEARCH_LIMIT:
        raise JobAgentError(
            "Search limit must be between 1 and 20",
            "search_limit_invalid",
        )

    normalized_provider = provider.strip().lower()
    search_provider = _PROVIDERS.get(normalized_provider)
    if search_provider is None:
        raise JobAgentError(
            "Search provider is not supported",
            "search_provider_unsupported",
        )

    return search_provider.search_jobs(normalized_query, limit=limit)
