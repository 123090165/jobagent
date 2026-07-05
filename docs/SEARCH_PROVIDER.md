# Search Provider

The current v4 job search architecture is part of the `JobSearchRun` flow under
`/api/v1`.

## Current Providers

- `mock`
- `cuhksz_career`
- `linkedin` (Serper-backed discovery of public job view links)
- `remoteok` (public JSON API)
- `serper_web` (optional, API-key backed)
- `browser_helper` (payload candidates collected by the local browser helper)
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

For the Search Preview UI, the preferred non-BOSS live-search shape is:

```json
{
  "search_provider": "multi_source",
  "selected_sources": ["cuhksz_career", "linkedin", "remoteok"]
}
```

The backend encodes the selected sources into the stored run provider name, for
example `multi_source:cuhksz_career,linkedin,remoteok`, and each returned
candidate keeps its own `source_provider`.

When BOSS is selected, the frontend first asks the Browser Helper to collect
BOSS candidates in the user's local browser session. It then calls
`POST /api/v1/job-search-runs/browser-helper` with:

```json
{
  "platforms": ["boss"],
  "selected_sources": ["cuhksz_career"],
  "candidates": ["...standardized BOSS candidates..."]
}
```

The backend composes a hybrid provider from the BOSS payload plus any selected
backend-native sources. A stored provider key such as
`browser_helper:boss,cuhksz_career` means BOSS came from the extension while
CUHKSZ was still searched by the backend. The result page displays both selected
sources and actual result source counts so this is visible after the run.

`GET /api/v1/job-search-providers/status` reports provider availability,
configured provider name, search URL, allowlisted domains, source kind, and
detail strategy.

## Frontend Source Rules

Source labels and provider-key parsing live in
`web/src/services/jobSearchSources.ts`. BOSS query localization and empty-result
diagnostics live in `web/src/services/bossSearchPlanning.ts`. Keep these rules
out of page components so Search Preview and Job Search results stay consistent.

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

## Candidate Identity And Deduping

All provider candidates pass through `candidate_recall_key()` in
`app/services/job_search_recall_metrics.py`. The dedupe key first canonicalizes
source URLs, then falls back to title/company/location when no URL exists.

The canonical URL rule is deliberately provider-wide:

- common URLs drop query strings and fragments;
- BOSS/Zhipin keeps only stable `/job_detail/<id>.html`;
- CUHKSZ keeps only `/job/view/id/<id>`;
- LinkedIn keeps `/jobs/view/<id>` and also maps search URLs with
  `currentJobId=<id>` to the same key.

Provider search dedupes candidates before filtering, and result assembly applies
the same key again so one job cannot appear twice with different scores after
ranking.

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

## Live Smoke Checks

Use the single-provider smoke check when the question is whether a provider can
fetch a real public result page right now:

```powershell
.venv\Scripts\python.exe experiments\provider_live_smoke.py `
  --provider cuhksz_career `
  --url "https://career.cuhk.edu.cn/job/search?title=%E7%AE%97%E6%B3%95&title_type=1&city=&d_industry=&nature=&d_skill=&d_category=" `
  --limit 3 `
  --min-candidates 1 `
  --require-detail
```

This script calls only the selected provider through the unified
`JobSearchProvider.search_jobs()` interface. It writes JSON and Markdown reports
with candidate counts, source URLs, detail status, raw-description length, and
source-level recall stats.

It also supports the frontend multi-source shape:

```powershell
.venv\Scripts\python.exe experiments\provider_live_smoke.py `
  --provider multi_source `
  --source cuhksz_career `
  --source linkedin `
  --source remoteok `
  --query "brand marketing intern Shanghai" `
  --limit 3 `
  --min-candidates 1
```

## Browser Helper Boundary

The local `slate-helper/` extension is kept as a reference implementation for
browser-assisted providers. JobAgent's active extension is `browser-helper/`.
It is currently scoped to BOSS:

- user opens the platform login page in their own browser;
- the extension checks BOSS cookies and verifies the live session with a hidden
  probe page;
- search tries the BOSS job-list JSON endpoint with browser credentials first;
- if the worker fetch cannot parse candidates, the helper opens one temporary
  background BOSS tab for page-context API fetch and DOM fallback;
- the backend receives standardized job candidates only, never platform cookies.

This is appropriate for sites such as BOSS where plain backend HTTP requests can
fail because of login, CORS, anti-bot checks, or SSR behavior. It should be
treated as a `browser_helper` provider family, not as a replacement for public
direct providers such as CUHKSZ Career or RemoteOK.

Current implementation status:

- `browser-helper/` can be loaded as a Chrome/Edge unpacked extension;
- Search Preview can detect the helper, check BOSS login state, open the BOSS
  login page, and ask the helper to collect BOSS search results;
- backend endpoint `POST /api/v1/job-search-runs/browser-helper` accepts
  standardized helper candidates and runs them through the existing ranking
  pipeline;
- Side Panel current-page capture can read the active tab's visible text after
  a user click and call `POST /api/v1/browser/job-captures/analyze`;
- browser job capture is normalized into the same `browser_helper` candidate
  path before JD analysis and profile matching;
- BOSS can be combined with backend-native sources in the same run;
- the first real collector target is BOSS (`zhipin.com`); other platforms are
  intentionally hidden until this path is stable.

Current-page capture data flow:

```text
Chrome Side Panel
-> activeTab visible-text extractor
-> extension service worker
-> FastAPI Browser Job Capture API
-> BrowserHelperJobCandidate normalization
-> existing JobAgent job-search analysis pipeline
-> Side Panel compact report
```

This path is intentionally generic. It reads visible text and page metadata; it
does not claim stable structured extraction for every recruiting site.

## Safety Rules

- Only fetch allowlisted public pages.
- Preserve source URLs.
- Treat parsed text as provider evidence, not invented content.
- Capture current pages only after explicit user action.
- Do not send browser cookies, API keys, or database secrets to the backend.
- Keep tests network-free by using fixtures or injected fetchers.
- Add future providers behind the same provider interface and status endpoint.
- Preserve candidate-pool and per-query trace details so poor recall can be
  diagnosed before changing the ranker.
