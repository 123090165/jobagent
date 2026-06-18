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

For the Slate-like profile flow, `POST /brief/from-search` can also accept a
`profile_context` that combines `confirmed_profile` and `user_confirmed_data`.
The brief service uses it to build an effective query that preserves the
user's explicit query and appends confirmed target roles, preferred locations,
skills, and constraints. This does not change provider internals, live provider
parsers, tracker integration, or persistence behavior.

v2.0 adds `ProfileSearchPlan`, so profile context is normalized into
`role_terms`, `skill_terms`, `location_terms`, `constraint_terms`, `warnings`,
and `effective_query` instead of being treated as a flat append only.
`brief/from-search` still sends only `effective_query` into providers, so this
does not add provider-specific query planning, multi-provider ranking changes,
or live provider parser changes.

v2.1 adds `POST /brief/search-plan` as a preview endpoint for that planner.
It returns `ProfileSearchPlan` before any provider search runs. The endpoint
does not call providers, does not persist data, does not add provider-specific
planning, and does not change `JobBriefReport` or the `/brief/from-search`
response schema.

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
  "warnings": [],
  "metadata": {},
  "items": [
    {
      "title": "AI Agent Developer",
      "company": "Mock AI Labs",
      "location": "Remote",
      "url": "https://mock.example.com/jobs/ai-agent-developer",
      "snippet": "Build agentic workflows with Python, FastAPI, and structured evaluation for resume and JD analysis products.",
      "responsibilities": [
        "Design agentic workflow services",
        "Build backend APIs for analysis flows"
      ],
      "requirements": [
        "Strong Python backend experience",
        "Experience with structured API design"
      ],
      "skills": ["Python", "FastAPI", "Pydantic", "LLM"],
      "jd_text": "Title: AI Agent Developer ...",
      "is_full_jd": true,
      "confidence": 0.94,
      "source": "mock",
      "retrieved_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

Provider-level observability fields:

- `SearchResultSet.warnings`
  - provider-level warnings that do not stop the main request
- `SearchResultSet.metadata`
  - provider execution statistics for debugging and observability

For `cuhksz_live`, `metadata` includes:

- `list_items_found`
- `detail_candidates`
- `detail_success`
- `detail_failed`
- `returned_count`

These fields are used for debugging and observability only. They do not change the downstream brief or analysis workflow behavior.

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

## Enriched JD Fields

`GeminiCLIProvider` now tries to return richer JD-oriented fields when possible:

- `responsibilities`
- `requirements`
- `skills`
- `jd_text`
- `is_full_jd`
- `confidence`

Important caveats:

- Gemini CLI still does not guarantee a full JD.
- If `is_full_jd` is `false`, do not treat the result as a complete JD.
- `jd_text` should still be validated by the user or checked via JD URL import before any future downstream workflow.
- Gemini-returned content is not the same as an official authoritative original job posting.
- Results are not automatically stored in SQLite.

## Current Limits

- `mock` remains the default stable provider.
- `gemini_cli` is experimental and disabled unless `JOBAGENT_ENABLE_GEMINI_CLI=1`.
- Results are stable mock data for testing and demo wiring.
- Gemini CLI output must be valid JSON and may be filtered if required fields are missing.
- Even with the upgraded prompt, Gemini may still return only partial summaries instead of a full JD.
- Search results are not saved to SQLite.
- Streamlit does not expose search yet; this round is API-only by design.

## Current CUHKSZ Provider Notes

- `cuhksz_career` is the only active live provider in the product flow right now.
- Provider-stage filtering is intentionally loose: valid CUHKSZ candidates are kept even when the user query is English or does not match list-page text directly.
- Precision is delegated downstream to candidate filtering, JD analysis, and profile matching.
- Planner internals now prepare bilingual search signals so future English providers can use expanded English aliases without changing the current CUHKSZ-only product scope.

## Why This Shape

This keeps provider-specific logic outside API routes and outside workflows, so later providers can be added with small, isolated changes.

## Future Extensions

- search result normalization for multiple providers
- `SearchResult -> JobImportCandidate`
- optional ranking / deduplication
- optional RAG or MCP integration in a later phase
