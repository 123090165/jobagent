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

`frontend/` is legacy Streamlit demo/admin code. It is still kept for now
because a small amount of backend quality-evaluation code imports helpers from
`frontend/profile_review_state.py`, but it is not the main user frontend.

## Current Providers

The current v4 job-search provider path uses:

- `mock`
- `cuhksz_career`

Older names such as `local_db`, `gemini_cli`, and `cuhksz_live` still appear in
legacy routes, tests, scripts, and older documentation. They are not the current
mainline provider set and should not be presented as the primary product path.

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

## Main Directories

- `app/api/v1`: current v4 FastAPI resource API
- `app/application`: v4 usecase layer
- `app/repositories`: persistence repositories
- `app/schemas`: Pydantic contracts
- `app/services`: business services and provider integrations
- `app/storage`: SQLite connection and storage helpers
- `web`: current Vue frontend
- `frontend`: legacy Streamlit demo/admin surface
- `tests`: backend and legacy regression coverage
- `docs`: product, architecture, cleanup, and legacy documentation
- `_archive`: archived historical notes and generated demo output snapshots

## Documentation

- [Cleanup Audit](docs/CLEANUP_AUDIT.md)
- [Legacy Map](docs/LEGACY_MAP.md)
- [v4 Product Refactor Plan](docs/V4_PRODUCT_REFACTOR_PLAN.md)
- [Search Provider](docs/SEARCH_PROVIDER.md)

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
- Treat `frontend/`, unversioned tracker routes, and old workflow docs as
  legacy until they are deliberately retired.
- Do not remove dependencies or legacy modules until import checks and the full
  test suite confirm the removal is safe.
