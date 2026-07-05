# JobAgent Browser Helper

This Chrome/Edge extension is the browser-assisted provider bridge for
JobAgent.

Current scope:

- detect helper availability from the JobAgent frontend;
- detect BOSS login state from local browser cookies without sending cookies to
  the backend;
- open the BOSS login page for the user;
- collect BOSS search result candidates through BOSS-specific query attempts;
- localize English profile/search terms into BOSS-friendly Chinese queries;
- try BOSS' search JSON endpoint from the extension service worker with browser
  credentials, then use one temporary background BOSS tab for page-context API
  fetch and DOM parsing fallback;
- capture the currently active job detail page from the Side Panel after a user
  click, then send visible text to local FastAPI for analysis;
- keep platform cookies inside the browser extension boundary.

Not implemented yet:

- BOSS detail-page enrichment beyond search-list data;
- additional recruiting platforms;
- company background enrichment.

## Current-Page Job Capture

The Side Panel flow is for a user-opened job detail page:

```text
Visible job detail page
-> JobAgent extension icon
-> Side Panel "Analyze current job"
-> activeTab visible-text capture
-> POST /api/v1/browser/job-captures/analyze
-> existing JobAgent job-search analysis pipeline
-> Side Panel match report
```

Required local setup:

- FastAPI running at `http://127.0.0.1:8000` or the configured backend URL.
- A ProfileSession that has reached confirmed-profile/job-search-ready state.
- The confirmed ProfileSession `session_id` entered in the Side Panel.

The generic extractor reads `window.location.href`, `document.title`, and
`document.body.innerText`. It records warnings when visible text is short,
structured fields are missing, or the page may not be a job detail page.

This flow does not run in the background continuously, does not send browser
cookies to the backend, and does not execute JavaScript produced by an LLM.

## Manual Verification

1. Open Chrome or Edge.
2. Go to `chrome://extensions`.
3. Enable Developer mode.
4. Load unpacked extension from this folder:

```text
D:\projects\jobagent\browser-helper
```

5. Start the backend and frontend.
6. Open the frontend in Chrome or Edge, not VSCode WebView:

```text
http://localhost:5173
```

If Vite falls back to `http://127.0.0.1:5174/`, that local URL is also covered
by the extension manifest.

7. Go to Search Preview.
8. Click `Check Helper`.
9. Click `Check BOSS Login`.
10. If needed, click `Open BOSS Login`, complete login in the browser, then
    click `Check BOSS Login` again.
11. Select `BOSS` in Recruiting Websites and click `Start Job Search`.

Expected result:

- helper status becomes detected;
- BOSS login status is detected;
- BOSS-specific search queries are tried in order, with empty-result queries
  skipped;
- BOSS search candidates are returned by the helper;
- a browser-helper job search run is created and may include backend-native
  sources such as CUHKSZ if they are also selected;
- the Job Search page shows selected sources, actual result source counts, and
  BOSS candidates from `boss_zhipin`.

If no valid BOSS candidates are parsed, the helper closes the temporary BOSS tab
and returns API/page diagnostics to the frontend. Use the reported BOSS queries
and diagnostics to distinguish login, verification, empty results, or a changed
BOSS response/page layout.

For current-page capture, open any visible job detail page, click the extension
icon, confirm the backend URL and session ID, then click `Analyze current job`.
The Side Panel should show the captured page preview, match score,
recommendation, gaps, and warnings.

## Security Boundary

The extension uses local browser login state for BOSS. Platform cookies must not
be sent to the backend. The backend receives only standardized job candidate
data.

The current-page capture path sends visible page text only. Model calls,
database writes, and matching decisions remain backend-only.

## Maintenance Notes

- BOSS query localization in the frontend lives in
  `web/src/services/bossSearchPlanning.ts`.
- BOSS search execution and DOM/API parsing live in `browser-helper/background.js`.
- Source labels and provider-key parsing live in
  `web/src/services/jobSearchSources.ts`.
- Candidate URL canonicalization and duplicate suppression live in
  `app/services/job_search_recall_metrics.py`.
