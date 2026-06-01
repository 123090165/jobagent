# Search Provider Abstraction

## Purpose

This phase adds a small, API-only search abstraction layer so JobAgent can grow into real job search providers later without changing the rest of the app architecture.

Current scope:

- `SearchProvider` interface
- `MockSearchProvider`
- `GeminiCLIProvider` (experimental, disabled by default)
- `POST /search/jobs`

Out of scope in this phase:

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
  -> MockSearchProvider.search_jobs(...) or GeminiCLIProvider.search_jobs(...)
  -> SearchResultSet
```

## Files

- `app/schemas/search.py`
- `app/services/search_providers/base.py`
- `app/services/search_providers/gemini_cli_provider.py`
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
- `search_provider_disabled`
- `search_provider_timeout`
- `search_provider_failed`
- `search_provider_output_invalid`

## GeminiCLIProvider Experimental

`provider="gemini_cli"` is available as an experimental provider, but it is disabled by default.

Environment variables:

```powershell
$env:JOBAGENT_ENABLE_GEMINI_CLI="1"
$env:JOBAGENT_GEMINI_CLI_COMMAND="gemini"
$env:JOBAGENT_GEMINI_CLI_TIMEOUT_SECONDS="20"
```

Example request:

```json
{
  "query": "agentic python backend jobs",
  "provider": "gemini_cli",
  "limit": 5
}
```

## Safety Boundaries

- Only the search `query` is passed to Gemini CLI.
- Resume text is not passed.
- API keys are not passed through the prompt.
- Local history and workspace-sensitive content are not passed.
- Search results are not automatically stored in SQLite.
- Search results do not automatically trigger JD import or analysis.
- Returned snippets may be incomplete and should not be treated as a full JD.

If the experimental search results look useful, the next step should still go through explicit user confirmation plus a later import path such as `JobImportCandidate` or existing JD URL import flows.

## Current Limits

- `mock` remains the default stable provider.
- `gemini_cli` is experimental and disabled unless `JOBAGENT_ENABLE_GEMINI_CLI=1`.
- Results are stable mock data for testing and demo wiring.
- Gemini CLI output must be valid JSON and may be filtered if required fields are missing.
- Search results are not saved to SQLite.
- Streamlit does not expose search yet; this round is API-only by design.

## Why This Shape

This keeps provider-specific logic outside API routes and outside workflows, so later providers can be added with small, isolated changes.

## Future Extensions

- search result normalization for multiple providers
- `SearchResult -> JobImportCandidate`
- optional ranking / deduplication
- optional RAG or MCP integration in a later phase
