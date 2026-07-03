# JobAgent Browser Helper

This Chrome/Edge extension is the browser-assisted provider bridge for
JobAgent.

Current scope:

- detect helper availability from the JobAgent frontend;
- return a demo candidate payload through the same browser-helper path that
  future BOSS/Liepin collectors will use;
- keep platform cookies inside the browser extension boundary.

Not implemented yet:

- real BOSS search parsing;
- real Liepin search parsing;
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

7. Go to Search Preview.
8. Click `Check Helper`.
9. Click `Import Demo Candidate`.

Expected result:

- helper status becomes detected;
- a browser-helper job search run is created;
- the Job Search page shows one demo candidate from `browser_helper_demo`.

## Security Boundary

The extension may use browser login state in later platform-specific collectors.
Platform cookies must not be sent to the backend. The backend receives only
standardized job candidate data.
