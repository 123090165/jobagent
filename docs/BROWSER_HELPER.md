# Browser Helper

browser-helper/ is a local Chrome/Edge extension for sources that require the
user's browser session. It is an adapter into the existing search and analysis
pipeline, not a separate analysis system.

## BOSS Search

~~~text
Search Preview selects BOSS
-> check extension
-> check or open BOSS login
-> user starts search
-> extension queries or parses BOSS in the browser session
-> normalized candidates return to Vue
-> POST /api/v1/job-search-runs/browser-helper
-> normal search pipeline
~~~

BOSS may be combined with selected backend-native providers. Empty BOSS results
do not invalidate valid candidates from other sources.

The extension may open temporary BOSS tabs while executing a user-triggered
search. It must close only tabs it created and must return a terminal success or
error to the frontend.

## Current-Page Capture

~~~text
User opens a job detail page
-> opens JobAgent Side Panel
-> clicks Analyze current job
-> extension reads visible page text and metadata
-> POST /api/v1/browser/job-captures/analyze
-> normal JD analysis and matching
-> compact Side Panel report
~~~

Capture runs only after explicit user action. For BOSS, validate that the page
is a job detail page and stop on login, verification, blank, search, or home
pages.

## Data Boundary

The extension may use BOSS cookies locally to determine login state and make
requests inside the user's browser session. It sends normalized candidate data,
source URLs, snippets, visible JD text, and warnings to JobAgent.

It must never send:

- platform cookie values;
- LLM or provider API keys;
- database credentials;
- raw browser history;
- page content unrelated to the user-triggered job operation.

Model calls, persistence, quality gates, and matching remain backend-only.

## Authentication Limitation

The Vue bridge uses the logged-in frontend when creating a browser-helper search
run. The Side Panel current-page request currently does not carry the web login
token and relies on backend local-user compatibility.

Before hosted or true multi-user use:

- bind the extension to a JobAgent login or short-lived extension token;
- remove manual session-id ownership as the only identity mechanism;
- reject anonymous resource access outside explicit local-development mode.

## Permissions

Current extension permissions include tabs, activeTab, cookies, scripting,
storage, sidePanel, localhost, and BOSS hosts. Review permissions whenever
behavior changes. Do not broaden host access for a speculative provider.

## Maintenance

- Keep message actions versioned and return explicit terminal responses.
- Put source parsing and safety guards in the extension, not the Vue page.
- Normalize candidates before they enter backend orchestration.
- Keep candidate identity and deduplication in shared backend services.
- Test login, verification, empty-result, timeout, partial-provider, and tab
  cleanup paths.
- Update the manifest version and this document for permission or behavior
  changes.

## Manual Verification

1. Start FastAPI and Vite.
2. Load browser-helper/ as an unpacked Chrome or Edge extension.
3. Open the JobAgent web application in the browser.
4. Complete a confirmed profile.
5. Check helper and BOSS login state from Search Preview.
6. Run BOSS-only and BOSS-plus-backend searches.
7. Open a BOSS detail page and test Side Panel capture.
8. Confirm no cookie values appear in backend payloads or logs.
