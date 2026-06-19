# Legacy Map

This map reflects the staged cleanup that removed the old Streamlit frontend,
unversioned route surface, full-analysis workflow, tracker/import flow, and old
provider stack.

## Current v4 mainline

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

Current runtime areas:

- `app/api/v1/`
- `app/application/`
- `app/repositories/`
- `app/schemas/`
- `app/services/`
- `app/storage/`
- `app/main.py`
- `web/`
- `tests/`

Current job-search providers:

- `mock`
- `cuhksz_career`

## Removed legacy areas

- `frontend/` Streamlit demo/admin UI.
- Old unversioned API routes under `app/api/routes_*.py`.
- Old full-analysis workflow under `app/workflows/`.
- Old workflow-only agents: match, report, resume optimize, project challenge,
  and missing info.
- Old tracker/import services and schemas for ApplicationRecord and
  JobImportCandidate.
- Old provider stack: `app/services/search_providers/`,
  `app/services/live_job/`, `public_job_storage_service.py`,
  `job_search_service.py`, and old CUHKSZ live/local/gemini provider tests.
- Old demo/evaluation scripts under `scripts/`.
- Docs that only described deleted Streamlit, tracker/import, workflow,
  LangGraph, batch brief, or old provider flows.
- Historical generated outputs and preparation notes deleted in earlier cleanup
  phases: `docs/demo_outputs/`, `docs/demo_runs/`, and `job_agent_prepare.md`.

## Dependencies removed

- `streamlit`
- `langgraph`
- `requests`

## Dependencies kept

- `beautifulsoup4`: required by the current `cuhksz_career` provider.
- `httpx`: required by FastAPI/Starlette `TestClient` usage in tests.
- `python-multipart`: required by FastAPI file upload endpoints.

## Remaining legacy areas

No known live legacy runtime path remains from the old Streamlit,
ApplicationRecord/JobImportCandidate, LangGraph workflow, or old provider
systems.

Some general docs may still contain historical wording and should be reviewed
opportunistically:

- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_OVERVIEW.md`
- `docs/DATA_SCHEMA.md`
- `docs/STORAGE.md`
- `docs/AGENTS.md`
- `docs/AGENT_BOUNDARIES.md`
- `docs/AGENT_TRACE.md`

## Future deletion plan

1. Review the remaining mixed-era architecture/API docs and either rewrite them
   for v4 or delete them if superseded by current docs.
2. Consider whether old SQLite tables created for analysis records need a
   migration note for existing local developer databases.
3. Keep future dependency removals gated by import checks, `pytest`, and
   `web` build verification.
