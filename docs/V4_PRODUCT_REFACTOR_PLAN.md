# JobAgent v4 Product Refactor Plan

JobAgent has been refactored around the v4 ProfileSession flow.

## Current Product Flow

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Job Search
-> Job Brief
```

## Current Architecture

```text
app/          FastAPI backend
app/api/v1   current public API surface
app/application
app/repositories
app/schemas
app/services
app/storage
web/          Vue user frontend
tests/
docs/
```

`web/` is the only current user-facing frontend. The legacy Streamlit
`frontend/` directory has been deleted.

`app/api/v1` is the only current public API surface. Old unversioned API routes
were deleted.

## Core Resources

- `ProfileSession`
- `ResumeDocument`
- `ParsedResumeReview`
- `ProfileDraft`
- `ConfirmedProfile`
- `JobSearchRun`
- `JobBrief` planned for v4.6

## Design Rules

1. The frontend calls `/api/v1`; it never imports backend services.
2. Backend workflow state is resource-based and recoverable from persistence.
3. Expensive generation is idempotent by default.
4. Replacing upstream resources invalidates downstream current resources.
5. Tests and build checks gate each step.

## Completed Milestones

### v4.0 Architecture Baseline

- `/api/v1` created.
- Vue app created under `web/`.
- ProfileSession resource introduced.

### v4.1 Resume Intake

- Resume text and txt/md upload endpoints.
- `ResumeDocument` persistence.
- Vue intake page.

### v4.2 Resume Review

- Resume parsing/review usecase.
- Parsed review display in Vue.

### v4.3 Profile Draft

- ProfileDraft generation, retrieval, update, and editing flow.

### v4.4 Confirmed Profile

- ConfirmedProfile creation and retrieval.
- Session enters job-search-ready state.

### v4.5 Job Search

- JobSearchRun resource.
- `mock` and `cuhksz_career` providers.
- Trace steps for planning, provider search, filtering, JD analysis, matching,
  and result assembly.
- Provider status API.
- LLM status API.

### Runtime Cleanup

- Deleted Streamlit `frontend/`.
- Deleted old unversioned API routes.
- Deleted old workflow/LangGraph runtime.
- Deleted old tracker/import flow.
- Deleted old provider paths and demo scripts.

## Current Next Step

### v4.6 Job Brief

Goal:

```text
JobSearchResult -> JobBrief
```

See `docs/NEXT_DEV_PLAN.md`.

## Hardening References

- `docs/API_CONTRACT_V1.md`
- `docs/V4_STATE_MACHINE.md`
- `docs/V4_ERROR_CONTRACT.md`
- `docs/V4_FRONTEND_ROUTE_GUARDS.md`
- `docs/SEARCH_PROVIDER.md`
