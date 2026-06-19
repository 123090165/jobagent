# Search Provider

The current v4 job search architecture is part of the `JobSearchRun` flow under
`/api/v1`.

## Current Providers

- `mock`
- `cuhksz_career`

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

`GET /api/v1/job-search-providers/status` reports provider availability,
configured provider name, search URL, and allowlisted domains.

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

## Safety Rules

- Only fetch allowlisted public pages.
- Preserve source URLs.
- Treat parsed text as provider evidence, not invented content.
- Keep tests network-free by using fixtures or injected fetchers.
- Add future providers behind the same provider interface and status endpoint.
