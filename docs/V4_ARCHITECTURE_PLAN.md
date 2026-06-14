# V4 Architecture Plan

## Goal

V4 resets JobAgent around a clear backend/frontend boundary:

- `app/` is the FastAPI backend.
- `web/` is the future user-facing Vue 3 frontend.
- `frontend/` is the legacy Streamlit demo/admin panel.
- The frontend and backend communicate through `/api/v1` only.

The first v4 resource is `ProfileSession`, which represents one user's resume-to-search-ready-profile workflow.

## Target Layers

```text
app/
  api/
    v1/
      profile_sessions.py
      resumes.py
      profile_drafts.py
      job_search.py
      briefs.py
  application/
    profile_session_usecases.py
    resume_ingestion_usecases.py
    profile_draft_usecases.py
    job_search_usecases.py
  services/
    resume_file_service.py
    profile_draft_service.py
    llm_provider.py
  schemas/
  models/
  repositories/

web/
  src/
    pages/
    components/
    api/
    stores/
    router/
    types/

frontend/
  streamlit_app.py
  README.md
```

## Resource Flow

```text
ProfileSession
  -> ResumeDocument
  -> ParsedResumeReview
  -> ProfileDraft
  -> ConfirmedProfile
  -> JobSearchRun
  -> JobBrief
```

`ProfileSession` is the primary workflow resource. It tracks the current step and links to the resources produced as the workflow advances.

## Streamlit Position

`frontend/` is retained for internal testing and demos. It should not receive new long-term user-facing product features. Streamlit currently mixes UI, orchestration, service calls, and session state, which makes history restore, multi-user flows, job search, and reporting harder to maintain.

## Vue 3 Position

`web/` is the formal user-facing frontend because Vue 3, Vite, TypeScript, Vue Router, Pinia, Axios, and Naive UI provide a maintainable app shell for routed flows, typed API clients, shared client state, and product-grade interaction patterns.

The Vue app must not import `app.services` or any backend modules. It talks to FastAPI through `/api/v1`.

## Current Skeleton

This round adds:

- `POST /api/v1/profile-sessions`
- `GET /api/v1/profile-sessions/{session_id}`
- `ProfileSession` schema and status/step enums
- In-memory `ProfileSession` repository stub
- Vue 3 shell under `web/`

The in-memory repository is temporary. A later persistence pass should move `ProfileSession` storage into the backend repository layer without changing the public `/api/v1` contract.

## Out Of Scope For This Round

- Full Profile Setup migration to Vue
- Parser rewrite
- Job description search
- Job matching
- Resume optimization
- Project follow-up
- Login or multi-user accounts
- PDF, DOCX, or OCR changes
