# JobAgent Browser Helper

This Chrome/Edge extension is the browser-assisted provider bridge for
JobAgent.

Current scope:

- detect helper availability from the JobAgent frontend;
- check local BOSS login state from the user's browser session;
- run user-triggered BOSS search and return normalized candidates to JobAgent;
- optionally open BOSS in a foreground tab after an explicit user click;
- capture the currently active job detail page from the Side Panel after a user
  click, then send visible text to local FastAPI for analysis.

Not implemented yet:

- additional recruiting platforms;
- company background enrichment.

## BOSS Search Provider

The Search Preview page can use BOSS as a browser-assisted provider:

```text
Search Preview BOSS checkbox
-> Check Helper / Check BOSS Login
-> Start Job Search
-> extension searchBoss action
-> BOSS joblist API or loaded-page DOM parsing in the user's browser session
-> POST /api/v1/job-search-runs/browser-helper
-> existing JobAgent ranking and JD analysis pipeline
```

This flow uses BOSS cookies only inside the local browser extension. Cookies are
not sent to the backend; the backend receives normalized job candidates, source
URLs, snippets, and warnings.

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
`document.body.innerText`. For BOSS detail pages, the extractor first checks
that the current URL is under `/job_detail/`, with or without a `.html` suffix,
then reads visible DOM fields such as title, company, location, salary, and job
description selectors.

This flow does not run in the background continuously, does not send browser
cookies to the backend, and does not execute JavaScript produced by an LLM. If
BOSS shows a login, verification, blank, search, or home page during current
page capture, the helper stops before sending the page to JobAgent.

For BOSS pages, Chrome requires host access before content scripts can read the
page. The helper has BOSS host permissions because automated search and login
probing need to run inside the user's local BOSS session.

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
9. If needed, click `Open BOSS Login`, complete login, then click
   `Check BOSS Login`.
10. Select BOSS and click `Start Job Search`.
11. For a single job detail page, click the JobAgent extension icon and use
    `Analyze current job` from the Side Panel.

Expected result:

- helper status becomes detected;
- BOSS login can be verified after login;
- Search Preview can create a browser-helper job search run with BOSS
  candidates;
- a BOSS detail page is captured only after the user opens it and clicks
  `Analyze current job`;
- the Side Panel shows the captured page preview, match score, recommendation,
  gaps, and warnings.

## Security Boundary

The extension may read BOSS cookies locally to verify login for user-triggered
BOSS search. Platform cookies must not be sent to the backend. The backend
receives only standardized job candidate data, source URLs, snippets, and
visible page text from user-triggered capture.

The current-page capture path sends visible page text only. Model calls,
database writes, and matching decisions remain backend-only.

## Maintenance Notes

- BOSS current-page capture and safety guards live in
  `browser-helper/background.js`.
- Source labels and provider-key parsing live in
  `web/src/services/jobSearchSources.ts`.
- Candidate URL canonicalization and duplicate suppression live in
  `app/services/job_search_recall_metrics.py`.
