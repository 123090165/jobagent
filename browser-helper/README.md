# JobAgent Browser Helper

browser-helper/ is the unpacked Chrome/Edge extension used for user-triggered
BOSS search and current-page job analysis.

It can:

- report helper availability;
- inspect local BOSS login state;
- run a user-triggered BOSS search and return normalized candidates;
- capture visible text from a user-opened job detail page;
- display a compact analysis result in the Side Panel.

BOSS cookie values stay inside the browser and must never be sent to FastAPI.
The extension does not support automatic applications, CAPTCHA bypass, or
continuous background crawling.

## Local Setup

1. Start FastAPI and the Vue development server.
2. Open chrome://extensions or edge://extensions.
3. Enable Developer mode.
4. Load this directory as an unpacked extension.
5. Complete a confirmed JobAgent profile in the browser.
6. Use Search Preview for BOSS search or the Side Panel for current-page
   analysis.

See ../docs/BROWSER_HELPER.md for the full data flow, permissions, security
boundary, authentication limitation, and verification checklist.
