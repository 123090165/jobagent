# JobAgent

JobAgent is being refactored toward the v4 ProfileSession product flow: a
FastAPI backend plus a Vue frontend for turning a resume into a confirmed,
search-ready profile and then into job search results and job briefs.

Current mainline:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

## Current Frontend

`web/` is the current Vue frontend and the main user-facing product surface.

The legacy Streamlit `frontend/` surface has been removed. Shared profile-review
helper logic that was still useful to backend quality checks now lives under
`app/services/profile_review_state_helpers.py`.

## Current Providers

The current v4 job-search provider path uses:

- `mock`
- `cuhksz_career`

Older provider names such as `local_db`, `gemini_cli`, and `cuhksz_live` were
removed with the legacy `/search/jobs` provider stack.

## Quick Start

Create and set up the virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run backend tests:

```powershell
.venv\Scripts\python.exe -m pytest
```

Start FastAPI:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Build the Vue frontend:

```powershell
cd web
npm install
npm run build
```

## Browser Job Capture Extension

The development Chrome/Edge extension lives in `browser-helper/`. It supports
user-triggered current-page job capture from the extension Side Panel.
Automated BOSS search, login probing, hidden tabs, polling, and BOSS API
fetches are disabled.

To test current-page capture:

1. Start FastAPI:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

2. Complete the normal resume flow until the session has a confirmed profile.
3. Copy the `session_id` from the JobAgent URL or API response.
4. Open `chrome://extensions`, enable Developer mode, and load unpacked from:

```text
D:\projects\jobagent\browser-helper
```

5. Open a visible job detail page and click the JobAgent extension icon.
6. In the Side Panel, set:

```text
Backend URL: http://127.0.0.1:8000
Profile session ID: <confirmed ProfileSession session_id>
```

7. Click `Analyze current job`.

The extension reads only visible page text after the user clicks. It sends
structured text, URL, page title, extractor version, and warnings to
`POST /api/v1/browser/job-captures/analyze`. The backend reuses the existing
Job Search pipeline for JD analysis and profile matching.

Current limitations:

- no automatic application submission;
- no batch crawling, automatic search, or automatic pagination;
- no CAPTCHA handling or anti-bot bypass;
- no browser cookies or LLM/API keys are sent to the backend;
- generic extraction may miss structured title/company/location fields.

## Main Directories

- `app/api/v1`: current v4 FastAPI resource API
- `app/application`: v4 usecase layer
- `app/repositories`: persistence repositories
- `app/schemas`: Pydantic contracts
- `app/services`: business services and provider integrations
- `app/storage`: SQLite connection and storage helpers
- `web`: current Vue frontend
- `tests`: backend regression coverage for the current v4 flow
- `docs`: product, architecture, and cleanup documentation

## Documentation

- [Docs Index](docs/INDEX.md)
- [API Contract V1](docs/API_CONTRACT_V1.md)
- [Search Provider](docs/SEARCH_PROVIDER.md)
- [Next Development Plan](docs/NEXT_DEV_PLAN.md)

## Current Boundaries

Current non-goals:

- auto apply
- login flows
- captcha handling
- browser automation
- email/calendar reminders
- multi-user auth
- unsupported resume fabrication

## Development Notes

- Keep v4 work centered on ProfileSession resources.
- Prefer `web/` for user-facing frontend work.
- Keep runtime work centered on `app/api/v1`, `app/application`,
  `app/repositories`, `app/services`, and `web`.
- Remove future legacy leftovers only after import checks and the full backend
  and frontend checks pass.
