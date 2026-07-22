# JobAgent Browser Helper

browser-helper/ is the unpacked Chrome/Edge extension used for user-triggered
BOSS search and current-page job analysis.

It can:

- report helper availability;
- inspect local BOSS login state;
- run a user-triggered BOSS search and return normalized candidates;
- capture visible text from a user-opened job detail page;
- create or continue Assistant conversations in the Side Panel;
- attach the explicitly captured page to one turn, or pin its search-result
  reference to the conversation;
- select a Saved Job by minimal metadata for an exact one-turn comparison while
  its JD and notes remain backend-only.

BOSS cookie values stay inside the browser and must never be sent to FastAPI.
The extension does not support automatic applications, CAPTCHA bypass, or
continuous background crawling.

## Local Setup

1. Start FastAPI and the Vue development server.
2. Open chrome://extensions or edge://extensions.
3. Enable Developer mode.
4. Load this directory as an unpacked extension.
5. Sign in and complete a confirmed JobAgent profile. From an unpaired Side
   Panel, click **Open and pair JobAgent**; login is followed by automatic
   pairing. The scoped pairing expires after eight hours.
6. Capture the current JD in the Side Panel, select a conversation, and chat with
   that exact page attached. Match analysis is optional; when requested, one
   confirmed Profile is selected automatically or multiple Profiles are shown by
   name.

See ../docs/BROWSER_HELPER.md for the full data flow, permissions, security
boundary, scoped authentication, and verification checklist.
