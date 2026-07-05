# Browser Job Capture Next Plan

## Purpose

Extend JobAgent from backend/web-driven job search runs to a user-triggered
browser job-detail capture flow:

```text
Chrome job detail page
-> user clicks JobAgent extension
-> extension captures visible JD context
-> FastAPI maps capture into the existing job-search analysis pipeline
-> extension shows a compact match report
```

This phase is only for browser page capture and analysis verification. It must
not add auto-apply, batch crawling, CAPTCHA handling, anti-bot bypasses, MCP, or
OpenAI Agents SDK.

## Current Code Facts

- Backend entrypoint is `app/main.py`. Routes are registered directly on
  `/api/v1/*` routers from `app/api/v1/`.
- There is no current CORS middleware and no product auth layer. Existing docs
  list multi-user auth as out of scope.
- The active product flow is ProfileSession based:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
```

- Current job matching is centralized in `app/application/job_search_usecases.py`.
  The traced pipeline is:

```text
Search planning
-> Provider search
-> Candidate filtering
-> JD analysis
-> Profile matching
-> Result assembly
```

- JD parsing itself lives in `app/agents/jd_analysis_agent.py` and returns
  `app.schemas.job.JobAnalysis`.
- Existing result shape is `JobSearchResult` in `app/schemas/job_search.py`.
  It already has match score, recommendation text, matched keywords, risks,
  evidence quotes, analysis mode, and confidence label.
- A browser-assisted path already exists:
  `POST /api/v1/job-search-runs/browser-helper`.
  It accepts `BrowserHelperJobSearchRunCreateRequest`, converts helper payload
  candidates into `RawJobCandidate`, then reuses the normal job-search workflow.
- `browser-helper/` is the active unpacked Chrome/Edge helper. It is currently
  scoped to BOSS search-list candidate collection, uses `tabs`, `cookies`, and
  `scripting`, and communicates with the Vue app through `bridge.js` +
  `window.postMessage`.
- `web/` is Vue 3 + Vite + Naive UI. API calls are centralized in
  `web/src/api/profileSessions.ts`; shared frontend types live in
  `web/src/types/profileSession.ts`.
- Tests are pytest based. Network and LLM calls are disabled in
  `tests/conftest.py`. Frontend coverage is currently mostly source-level
  assertions in `tests/test_frontend_search_preview_flow.py`.
- Current worktree already has unrelated modified files, so the next coding
  phase should start by preserving those changes and creating or switching to
  the intended feature branch only after reviewing status.

## Key Architecture Decision

Do not build a parallel "JD analysis" subsystem.

The browser job-detail capture should be a thin adapter into the existing
`browser_helper` job-search path. The smallest coherent backend shape is:

```text
BrowserJobCaptureRequest
-> normalize to BrowserHelperJobCandidate / RawJobCandidate
-> create_browser_helper_job_search_run(...)
-> return compact capture + first JobSearchResult + trace warnings
```

This keeps profile lookup, JD analysis, filtering, matching, persistence, LLM
fallback, and trace behavior in one place.

## Proposed Backend Scope

### 1. Schemas

Add browser job-detail capture schemas to `app/schemas/job_search.py` unless the
file becomes too crowded. Keep them close to `BrowserHelperJobCandidate` because
this is an input adapter for the existing helper path.

Suggested models:

- `BrowserJobCaptureRequest`
- `BrowserJobCaptureSummary`
- `BrowserJobCaptureAnalyzeResponse`

Required request fields:

- `session_id`
- `source`
- `source_url`
- `page_title`
- `title`
- `company`
- `location`
- `salary`
- `jd_text`
- `visible_text`
- `captured_at`
- `extractor_version`
- `warnings`
- `use_llm`

Validation rules:

- reject empty or too-short `jd_text`;
- cap `jd_text` and `visible_text` lengths;
- keep incomplete title/company/location as warnings, not hard failures;
- reject obviously invalid `source_url` unless the existing schema style favors
  plain strings. If strict URL validation causes compatibility friction, accept
  string input and validate enough for diagnostics.

### 2. Normalization Service

Add a small helper in `app/application/job_search_usecases.py` or a focused
service such as `app/services/browser_job_capture.py`.

Responsibilities:

- convert one capture into one `BrowserHelperJobCandidate`;
- set `source_provider` to a stable value such as `browser_capture:{source}`;
- use `jd_text` as `raw_description`;
- use a short `jd_text` preview as `snippet`;
- preserve `page_title`, `extractor_version`, `captured_at`, and capture
  warnings in `provider_warnings`.

Keep the conversion deterministic and unit tested.

### 3. API Route

Add a route in the current API style:

```text
POST /api/v1/browser/job-captures/analyze
```

Prefer a new router file:

```text
app/api/v1/browser_job_captures.py
```

Register it in `app/main.py`.

The route should:

- accept `BrowserJobCaptureRequest`;
- require a valid existing ProfileSession with confirmed profile through the
  reused job-search workflow;
- call the normalization helper;
- call `create_browser_helper_job_search_run(...)` with one candidate and
  `platforms=[source]`;
- return a compact response for the extension.

The response should not create an application record. Persisting the underlying
job-search run is acceptable because that is already the existing analysis
record for this product flow.

### 4. CORS And Local Auth Boundary

Because the project currently has no real auth, do not invent production auth in
this phase.

Minimum acceptable implementation:

- add explicit CORS configuration in `app/main.py`;
- read allowed origins from env, for example
  `JOBAGENT_CORS_ALLOW_ORIGINS`;
- include local web origins and documented extension origins only in dev;
- do not use wildcard origins with credentials;
- do not put LLM or database secrets in the extension;
- document that `session_id` is the current development binding to a confirmed
  local profile.

If an extension ID is not stable during unpacked development, allow users to
configure it by env after loading the extension.

## Proposed Extension Scope

The current `browser-helper/` is active and already integrated with the web app,
but it is BOSS search-list oriented and asks for broader BOSS/cookie
permissions.

For the new current-page job-detail flow, prefer either:

1. add a new, low-permission mode inside `browser-helper/`, or
2. create `extension/` only if the existing helper would become too mixed.

Decision rule:

- use `browser-helper/` if the side panel and current-page capture can share the
  existing manifest without increasing permissions further;
- use `extension/` if we want a clean MV3 extension with only `activeTab`,
  `scripting`, `storage`, `sidePanel`, and localhost backend host permissions.

Minimum extension modules:

- generic page extractor that reads `window.location.href`, `document.title`,
  and `document.body.innerText`;
- source inference from URL host: `zhipin.com`, `linkedin.com`, company site,
  unknown;
- text cleanup and max length cap;
- structured warnings for short text, missing fields, likely non-job page, and
  extraction errors;
- background/service worker API client for local FastAPI;
- side panel with one `Analyze current job` action and compact result/error
  states.

The extension should not run continuously. Capture must happen only after user
action.

## Frontend And UX Notes

The extension side panel should be operational, not a marketing or chat UI.

Required states:

- idle with backend/session configuration;
- capturing page;
- backend analyzing;
- success with capture preview and match result;
- page extraction failure;
- backend unreachable;
- backend validation/business error.

Display fields:

- page title;
- source URL;
- inferred source;
- JD preview;
- match score;
- recommendation;
- matched strengths or keywords;
- critical gaps/risks;
- resume actions if available from the existing result shape;
- warnings.

If the backend only returns `JobSearchResult` fields in this phase, map:

- `match_score` -> match score;
- `recommended_action` -> recommendation;
- `matched_keywords` and `match_reasons` -> strengths;
- `risks` -> gaps;
- `evidence_quotes` -> evidence.

## Implementation Order

1. Protect the branch/worktree.
   - Check `git status`.
   - Create or switch to `feat/browser-job-capture` only if it does not risk
     mixing unrelated current changes.

2. Backend contract.
   - Add capture request/response schemas.
   - Add deterministic validation and normalization.
   - Add unit tests for schema and conversion.

3. Backend route.
   - Add `POST /api/v1/browser/job-captures/analyze`.
   - Register router.
   - Reuse `create_browser_helper_job_search_run`.
   - Add API tests for success, missing confirmed profile, short JD, incomplete
     fields with warnings, and invalid URL.

4. CORS/dev config.
   - Add explicit configurable origins.
   - Update `.env.example`.
   - Add a small test or source assertion that wildcard credentialed CORS is
     not used.

5. Extension capture.
   - Decide `browser-helper/` vs new `extension/` after branch is created.
   - Implement generic extractor and warning taxonomy.
   - Implement backend API client with configurable backend URL and session ID.
   - Add side panel result UI.

6. Extension tests/static checks.
   - Add source-level tests similar to the existing frontend helper tests.
   - If using TypeScript/Vite, add build script and run it.

7. Documentation.
   - Update README with development install/run steps.
   - Update `docs/API_CONTRACT_V1.md` and `docs/SEARCH_PROVIDER.md` with the
     new current-page capture flow.
   - Document limitations clearly: no auto-apply, no batch crawling, no
     CAPTCHA or anti-bot bypass.

8. Verification.
   - Run focused backend tests first.
   - Run full pytest if practical.
   - Build frontend/extension if touched.
   - Manually test against a simple public job-detail page and record warnings.

## Initial File Plan

Likely backend files:

- `app/main.py`
- `app/api/v1/browser_job_captures.py`
- `app/application/job_search_usecases.py`
- `app/schemas/job_search.py`
- `.env.example`
- `tests/test_browser_job_capture_api.py`
- `tests/test_browser_job_capture_service.py`

Likely extension files, pending `browser-helper/` vs `extension/` decision:

- `browser-helper/manifest.json` or `extension/manifest.json`
- `browser-helper/background.js` or `extension/src/background/service-worker.ts`
- current-page extractor module
- side panel module
- extension README

Likely docs:

- `README.md`
- `docs/API_CONTRACT_V1.md`
- `docs/SEARCH_PROVIDER.md`
- `docs/PROJECT_STRUCTURE.md`

## Open Questions Before Coding

- Should current-page capture live in the existing `browser-helper/` or in a new
  low-permission `extension/` directory?
- What is the intended way for the extension to know `session_id` in local dev:
  manual setting, storage after user paste, or reading from the current
  JobAgent web URL?
- Should the endpoint return only a compact response, or also include the full
  `JobSearchRunResponse` for debugging?
- Should `use_llm` default to false for local reliability, matching current
  test behavior?
- What exact extension origin should be allowed in CORS once the unpacked
  extension ID is known?

## Non-Goals For This Phase

- MCP server/client.
- OpenAI Agents SDK.
- Multi-agent orchestration.
- Automatic job application.
- Automatic searching, pagination, or bulk capture.
- CAPTCHA handling or anti-bot bypass.
- Sending browser cookies to the backend.
- Storing raw page HTML.
- Production multi-user auth.
- Redis, Celery, or background task queues.
