# Search Provider

The current v4 job search architecture is part of the `JobSearchRun` flow under
`/api/v1`.

## Current Providers

- `mock`
- `cuhksz_career`
- `linkedin` (Serper-backed discovery of public job view links)
- `remoteok` (public JSON API)
- `serper_web` (optional, API-key backed)
- `multi_source` (aggregates selected recruiting websites)

Removed legacy providers and surfaces:

- `GeminiCLIProvider`
- `local_db`
- `cuhksz_live`
- `POST /search/jobs`

## Current Pipeline

`JobSearchRun` execution is traced in these steps:

```text
Search planning
-> Provider search
-> Candidate filtering
-> JD analysis
-> Profile matching
-> Result assembly
```

### Search Planning

Builds search intent from the confirmed profile and optional request fields.
Planning must not invent missing profile history, credentials, or experience.

### Provider Search

Calls the selected provider and returns raw job candidates with provider
metadata.

Provider search is intentionally source-type based rather than platform-hardcoded:

- `native_job_board`: use a site's public search/list/detail pages when they are stable enough.
- `native_api`: use a public provider API and preserve provider attribution.
- `search_engine`: use a search API to discover public job links and snippets.
- `hybrid`: aggregate multiple selected sources into one deduped candidate pool.
- `direct_crawler`: future provider type for allowlisted public pages or seed URLs.
- `mock`: deterministic local provider for tests and demos.

The first retrieval pass should favor broad recall. Detailed profile skills and
constraints should be retained as ranking signals instead of being forced into
every provider query.

### Candidate Filtering

Ranks provider-returned candidates against the confirmed profile and search plan.
It must not create or merge candidates.

### JD Analysis

Analyzes candidate descriptions using the current JD analysis path with
deterministic fallback.

### Profile Matching

Scores candidate fit against confirmed profile skills, target roles, and search
signals.

### Result Assembly

Returns job cards backed by provider results. Source provider and source URL
must be preserved.

## Provider Selection

`POST /api/v1/job-search-runs` accepts `search_provider`.

Allowed values:

- `mock`
- `cuhksz_career`
- `linkedin`
- `remoteok`
- `serper_web`
- `multi_source`

For the Search Preview UI, the preferred live-search shape is:

```json
{
  "search_provider": "multi_source",
  "selected_sources": ["cuhksz_career", "linkedin", "remoteok"]
}
```

The backend encodes the selected sources into the stored run provider name, for
example `multi_source:cuhksz_career,linkedin,remoteok`, and each returned
candidate keeps its own `source_provider`.

`GET /api/v1/job-search-providers/status` reports provider availability,
configured provider name, search URL, allowlisted domains, source kind, and
detail strategy.

## Mock Provider

`mock` is deterministic and network-free. It is used for tests, local demos, and
fallback development.

## CUHKSZ Career Provider

`cuhksz_career` fetches public CUHKSZ Career pages:

- base URL: `https://career.cuhk.edu.cn`
- search URL: `https://career.cuhk.edu.cn/job/search`
- allowlisted domain: `career.cuhk.edu.cn`

Boundaries:

- no login
- no captcha bypass
- no browser automation
- no anti-bot bypassing
- list/detail parsing only
- no user secrets or API keys in provider requests

The provider keeps recall broad. Downstream candidate filtering, JD analysis,
profile matching, and result assembly handle precision and ranking.

## Serper Web Search Provider

`serper_web` uses Serper's Google Search API as a discovery source. It is not a
default dependency and is configured only when an API key exists:

- `SERPER_API_KEY` or `JOBAGENT_SERPER_API_KEY`
- optional `JOBAGENT_WEB_SEARCH_SITES=career.example.com,jobs.example.org`

Boundaries:

- no direct Google result-page scraping
- no login/captcha bypass
- search result snippets are preserved when detail pages are not fetched
- source URLs are kept so users can open the original posting
- tests must use injected fetchers and must not call Serper

This provider is useful when native job-board search is too strict. For example,
it can discover public pages with broad queries and optional `site:` filters,
while downstream ranking still decides whether the JD actually matches the
confirmed profile.

## LinkedIn Discovery Provider

`linkedin` is intentionally implemented as search-engine discovery, not direct
LinkedIn page scraping:

- uses Serper with `site:linkedin.com/jobs`
- keeps only concrete `/jobs/view/...` links
- filters out profile pages and broad list pages
- preserves the LinkedIn URL for the user to open
- does not fetch LinkedIn detail pages

This keeps LinkedIn useful as a recall source while avoiding login, browser
automation, and anti-bot bypass behavior.

## RemoteOK Provider

`remoteok` uses `https://remoteok.com/api` and then filters returned records
locally against the generated provider query.

Boundaries:

- no HTML scraping
- source links and RemoteOK attribution warnings are preserved
- tests use injected JSON responses and must not call the live API

## Multi-Source Provider

`multi_source` runs the selected source providers and merges their candidates
before the shared filtering/ranking stage. It is currently the main frontend
path for live search because it lets the user choose CUHKSZ Career, LinkedIn,
and RemoteOK independently.

## Recall Calibration

Use the provider recall calibration experiment before changing query limits or
ranking behavior:

```powershell
.venv\Scripts\python.exe experiments\provider_recall_calibration.py `
  --env-file .env.deepseek.local `
  --queries-per-case 2 `
  --limit-per-query 5
```

The experiment supports:

- `--provider multi_source` with `--source cuhksz_career`, `--source linkedin`,
  and/or `--source remoteok`;
- `--provider cuhksz_career`;
- `--provider linkedin`;
- `--provider remoteok`;
- `--provider serper_web`.

The report measures raw candidates, deduped candidates, duplicates, truncated
candidates, missing source URLs, missing detail text, detail coverage, provider
warnings, source-provider counts, and top candidate links. It uses deterministic
search intent during setup and does not call DeepSeek or build Job Brief.

Runtime `Provider search` trace details use the same source-level recall metric
shape so frontend/manual debugging and experiment reports share one vocabulary.

## Safety Rules

- Only fetch allowlisted public pages.
- Preserve source URLs.
- Treat parsed text as provider evidence, not invented content.
- Keep tests network-free by using fixtures or injected fetchers.
- Add future providers behind the same provider interface and status endpoint.
- Preserve candidate-pool and per-query trace details so poor recall can be
  diagnosed before changing the ranker.
