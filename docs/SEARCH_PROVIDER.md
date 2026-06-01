# Search Provider Abstraction

## Purpose

This phase adds a small, API-only search abstraction layer so JobAgent can grow into real job search providers later without changing the rest of the app architecture.

Current scope:

- `SearchProvider` interface
- `MockSearchProvider`
- `POST /search/jobs`

Out of scope in this phase:

- Gemini CLI execution
- Google Search
- Tavily / Exa
- RAG / MCP
- Browser automation
- Crawling, login, captcha handling, or anti-bot bypass
- SQLite persistence for search results
- Streamlit integration

## Data Flow

```text
API request
  -> SearchJobsRequest
  -> job_search_service.search_jobs(...)
  -> SearchProvider lookup
  -> MockSearchProvider.search_jobs(...)
  -> SearchResultSet
```

## Files

- `app/schemas/search.py`
- `app/services/search_providers/base.py`
- `app/services/search_providers/mock_provider.py`
- `app/services/job_search_service.py`
- `app/api/routes_search.py`

## API Example

`POST /search/jobs`

Request:

```json
{
  "query": "python backend llm",
  "provider": "mock",
  "limit": 3
}
```

Response:

```json
{
  "query": "python backend llm",
  "provider": "mock",
  "items": [
    {
      "title": "AI Agent Developer",
      "company": "Mock AI Labs",
      "location": "Remote",
      "url": "https://mock.example.com/jobs/ai-agent-developer",
      "snippet": "Build agentic workflows with Python, FastAPI, and structured evaluation for resume and JD analysis products.",
      "source": "mock",
      "retrieved_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

Business errors still use the shared JobAgent error shape:

```json
{
  "detail": "Search provider is not supported",
  "error_code": "search_provider_unsupported"
}
```

## Error Codes

- `search_query_invalid`
- `search_limit_invalid`
- `search_provider_unsupported`

## Current Limits

- Only the `mock` provider is implemented.
- No real internet access or CLI execution is used.
- Results are stable mock data for testing and demo wiring.
- Search results are not saved to SQLite.
- Streamlit does not expose search yet; this round is API-only by design.

## Why This Shape

This keeps provider-specific logic outside API routes and outside workflows, so later providers can be added with small, isolated changes.

## Future Extensions

- `GeminiCLIProvider`
- search result normalization for multiple providers
- optional ranking / deduplication
- optional RAG or MCP integration in a later phase
