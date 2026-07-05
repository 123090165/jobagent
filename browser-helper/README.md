# JobAgent Browser Helper

This Chrome/Edge extension is the browser-assisted provider bridge for
JobAgent.

Current scope:

- detect helper availability from the JobAgent frontend;
- optionally open BOSS in a foreground tab after an explicit user click;
- capture the currently active job detail page from the Side Panel after a user
  click, then send visible text to local FastAPI for analysis.

Not implemented yet:

- automated BOSS search, login probing, background tabs, polling, or BOSS API
  fetches;
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
`document.body.innerText`. For BOSS detail pages, the extractor first checks
that the current URL is under `/job_detail/`, with or without a `.html` suffix,
then reads visible DOM fields such as title, company, location, salary, and job
description selectors.

This flow does not run in the background continuously, does not send browser
cookies to the backend, does not fetch BOSS APIs, does not open hidden BOSS
tabs, does not poll BOSS pages, and does not execute JavaScript produced by an
LLM. If BOSS shows a login, verification, blank, search, or home page, the
helper stops before sending the page to JobAgent.

For BOSS pages, Chrome requires host access before content scripts can read the
page. The helper keeps BOSS as an optional host permission, requests
`https://www.zhipin.com/*` only after the user clicks `Analyze current job`, and
removes that permission after the analysis attempt finishes.

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
9. If needed, click `Open BOSS` and manually navigate to a BOSS job detail
   page.
10. Click the JobAgent extension icon and use `Analyze current job` from the
    Side Panel.

Expected result:

- helper status becomes detected;
- automated BOSS search remains disabled;
- a BOSS detail page is captured only after the user opens it and clicks
  `Analyze current job`;
- the Side Panel shows the captured page preview, match score, recommendation,
  gaps, and warnings.

## Security Boundary

The extension does not read BOSS cookies for current-page capture. Platform
cookies must not be sent to the backend. The backend receives only standardized
job candidate data from the visible page.

The current-page capture path sends visible page text only. Model calls,
database writes, and matching decisions remain backend-only.

## Maintenance Notes

- BOSS current-page capture and safety guards live in
  `browser-helper/background.js`.
- Source labels and provider-key parsing live in
  `web/src/services/jobSearchSources.ts`.
- Candidate URL canonicalization and duplicate suppression live in
  `app/services/job_search_recall_metrics.py`.
