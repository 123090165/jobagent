# JobAgent Browser Helper

This Chrome/Edge extension is the browser-assisted provider bridge for
JobAgent.

Current scope:

- detect helper availability from the JobAgent frontend;
- detect BOSS login state from local browser cookies without sending cookies to
  the backend;
- open the BOSS login page for the user;
- collect BOSS search result candidates through BOSS-specific query attempts.
  The helper first tries BOSS' search JSON endpoint from the extension service
  worker with browser credentials, then uses one temporary background BOSS tab
  for page-context API fetch and DOM parsing fallback;
- keep platform cookies inside the browser extension boundary.

Not implemented yet:

- BOSS detail-page enrichment beyond search-list data;
- additional recruiting platforms;
- company background enrichment.

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
- a browser-helper job search run is created;
- the Job Search page shows BOSS candidates from `boss_zhipin`.

If no valid BOSS candidates are parsed, the helper closes the temporary BOSS tab
and returns API/page diagnostics to the frontend. Use the reported BOSS queries
and diagnostics to distinguish login, verification, empty results, or a changed
BOSS response/page layout.

## Security Boundary

The extension uses local browser login state for BOSS. Platform cookies must not
be sent to the backend. The backend receives only standardized job candidate
data.
