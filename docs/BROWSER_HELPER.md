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
User pairs Browser Helper from the authenticated Assistant page
-> opens a job detail page and the JobAgent Side Panel
-> clicks Capture current JD
-> extension reads visible page text and metadata
-> POST /api/v1/browser/job-captures stores an owned capture without LLM analysis
-> POST /api/v1/chat/conversations/{id}/context/browser-captures binds only the owned capture ID
-> Chat is unlocked with the full captured JD visible in a scrollable preview
-> user selects or creates a conversation and asks questions directly in the Side Panel composer
-> POST /api/v1/chat/conversations/{id}/turns
-> optional Analyze JD match reuses the stored capture and an Analysis profile
-> POST /api/v1/browser/job-captures/{capture_id}/analyze
~~~

Capture runs only after explicit user action and does not require a Profile. For BOSS, validate that the page
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

## Authentication

The authenticated Assistant page creates a dedicated eight-hour
`browser_helper` session and passes it through the installed page bridge. The
extension keeps that token in `chrome.storage.session`, never local storage.
Creating this session requires a valid full login token; local-user fallback is
not accepted. When an unpaired Side Panel opens JobAgent, it uses
`pair_browser_helper=1`; the login redirect preserves that intent and Assistant
pairs automatically after authentication. The Assistant verifies the page
bridge before creating the scoped session. Pairing updates extension session
storage, which causes an already-open Side Panel to reload its authenticated
state automatically.
The token is accepted only by the small Chat subset needed to create/list
conversations, read/send turns, pin an owned browser capture, and by current-page
capture. Chat deletion, memory clearing, context catalogs, ordinary profile,
saved-job, auth, and other APIs require a full session. Every repository lookup
remains scoped by the token's `user_id`.

The Side Panel stores only UI selections in local extension storage. It does not
persist chat bodies or JD text. A captured page is stored once by the backend and
referenced by an owned `capture_id`; the backend re-reads it under the current
user before answering. Match analysis remains optional and creates normal search
analysis records only when explicitly requested.

The Side Panel may also request a bounded Saved Job selector catalog. This
catalog exposes only ID, title, company, and status. Selecting an item sends its
ID as a one-turn attachment; the full JD, notes, and analysis remain backend-only
and are re-read after ownership validation.

For JD analysis, the backend maps each ready workflow session to its Resume
Profile name. The Side Panel calls this an `Analysis profile`; it never displays
the internal session ID. A single available Profile is selected automatically
and shown as a compact status, while the selector appears only when multiple
Profiles are available.

For a hosted deployment, replace the localhost allowlist and page-bridge pairing
with an origin-bound one-time exchange, and add explicit token revocation UI.

Opening Assistant from the Side Panel reuses and focuses an existing local
JobAgent tab when possible. It creates a new tab only when no recognized
JobAgent application tab is open.

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
7. Pair the helper from Assistant, open a BOSS detail page, and test Side Panel capture.
8. Attach once, pin once, continue the same conversation, and open it in full Chat.
9. Confirm no cookie values or primary login token appear in extension storage,
   backend payloads, or logs.
