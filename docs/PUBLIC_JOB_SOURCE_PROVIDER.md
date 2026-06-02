# Public Job Source Provider

## 1. Goal

This document reserves the next interface boundary for public job sources that are:

- public
- no-login
- low anti-bot
- suitable for small-scale manual search and review

The target direction is to connect resume-driven search queries with public job listings, then normalize them into `SearchResultItem` records before they enter `Batch Job Brief`.

Example future sources:

- CUHKSZ public career pages
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

### `CUHKSZCareerProvider`

Reserved for public CUHKSZ-style career pages that are accessible without login.

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

When real public providers are added, JobAgent should also track extraction quality fields such as:

- `extraction_method`
- `quality_score`
- `is_valid_jd`
- `warnings`

These fields are intentionally not implemented in this round. They are reserved for a later JD extraction quality gate.

## 6. Data Flow Direction

Planned flow:

1. Resume text
2. Rule-based or LLM-assisted search query generation
3. Public source provider fetch
4. Normalize to `SearchResultItem`
5. User review / confirmation
6. Batch Job Brief or later import flow

The key idea is that search acquisition stays separate from application tracking and separate from any automatic action.

## 7. Current Status

Current implemented search providers:

- `mock`
- `gemini_cli` experimental

No public HTML provider is implemented in this round. This document exists to keep the next provider boundary explicit and safe.
