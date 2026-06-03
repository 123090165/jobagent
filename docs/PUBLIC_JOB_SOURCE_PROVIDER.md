# Public Job Source Provider

## 1. Goal

This document reserves the next interface boundary for public job sources that are:

- public
- no-login
- low anti-bot
- suitable for small-scale manual search and review

The target direction is to connect resume-driven search queries with public job listings, then normalize them into `SearchResultItem` records before they enter `Batch Job Brief`.

Example sources:

- CUHKSZ public career pages, currently implemented as a small collector MVP
- generic public HTML job pages
- manually exported CSV lists
- manually supplied job URLs

## 2. Explicit Non-Goals

JobAgent will not use this provider family for:

- LinkedIn auto-login
- cookies or session replay
- captcha handling
- anti-bot bypass
- browser automation
- automatic application submission

If a source requires authentication or active bypass techniques, it is out of scope.

## 3. Planned Provider Variants

### CUHKSZ career collector MVP + `local_db`

Implemented in this round as a collector plus a local replay provider.

Current behavior:

- fetches one public list page
- parses the current page's first N job cards
- fetches each public detail page
- extracts cleaned `jd_text`
- upserts rows into `public_job_posts`
- exposes stored rows through provider name `local_db`
- allows local stored jobs to flow into `POST /search/jobs` and `POST /brief/from-search`

### `GenericPublicHtmlJobProvider`

Reserved for simple public job pages that can be fetched as plain HTML and converted into text without browser automation.

### `ManualCSVProvider`

Reserved for user-supplied CSV data that already contains title, company, URL, and snippet-like fields.

### `ManualURLProvider`

Reserved for user-supplied public job URLs that can be fetched one-by-one with the same safety rules used by JD URL import.

## 4. Unified Output Contract

Future providers should normalize outputs into the existing `SearchResultItem` shape and continue to support:

- `title`
- `company`
- `location`
- `url`
- `snippet`
- `source`
- `jd_text`
- `is_full_jd`
- `confidence`

This keeps downstream services stable:

- `POST /search/jobs`
- `POST /brief/from-search`
- future `JobImportCandidate` review steps

## 5. Quality Signals Reserved For Later

Collectors and future providers should track extraction quality fields such as:

- `extraction_method`
- `quality_score`
- `is_valid_jd`
- `warnings`

The CUHKSZ collector stores lightweight `extraction_method`, `confidence`, `is_full_jd`, and `warnings` signals. A stricter JD extraction quality gate is still reserved for a later round.

## 6. Data Flow Direction

Planned provider flow:

1. Resume text
2. Rule-based or LLM-assisted search query generation
3. Public source provider fetch
4. Normalize to `SearchResultItem`
5. User review / confirmation
6. Batch Job Brief or later import flow

Current collector flow:

1. CUHKSZ public list page
2. Public detail page
3. Cleaned `jd_text`
4. `public_job_posts`
5. `local_db` provider
6. Batch Job Brief

The key idea is that search acquisition stays separate from application tracking and separate from any automatic action.

## 7. Current Status

Current implemented search providers:

- `mock`
- `local_db`
- `gemini_cli` experimental

Current public job source status:

- CUHKSZ collector MVP is implemented.
- It writes to `public_job_posts`.
- `local_db` is implemented as a local replay provider over stored public jobs.
- Local stored public jobs are connected to `/search/jobs` and `/brief/from-search`.
