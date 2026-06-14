# Frontend Separation Plan

## Decision

JobAgent now separates frontend responsibilities:

- `frontend/` remains the legacy Streamlit demo/admin panel.
- `web/` is the Vue 3 user-facing product frontend.
- `app/` remains the FastAPI backend.

## Why Streamlit Becomes Legacy

The Streamlit app helped validate Profile Creation quickly, but it currently combines:

- product UI
- flow orchestration
- backend service calls
- `session_state` workflow state

That shape is useful for demos and internal checks, but it is not the target surface for a routed product with history restore, job search, reporting, and future multi-user support.

## Why Vue 3

Vue 3 with Vite and TypeScript gives the product frontend:

- routed pages for resume intake, review, draft, confirmation, search, and briefs
- typed API clients for `/api/v1`
- Pinia stores for client workflow state
- reusable components for progress and review surfaces
- Naive UI primitives for consistent product controls

## Boundary Rules

- `web/` calls FastAPI through `/api/v1`.
- `web/` must not import `app.services`, `app.schemas`, or any backend Python modules.
- Backend orchestration belongs in `app/application`.
- Backend implementation details stay behind `app/api/v1`.
- Streamlit remains available for legacy demos and admin-style internal testing.

## Migration Route

1. Keep the existing Streamlit Profile Creation MVP intact.
2. Use `ProfileSession` as the main v4 workflow resource.
3. Add `/api/v1` endpoints around the ProfileSession flow.
4. Move user-facing Profile Creation screens into Vue page by page.
5. Keep parser and LLM services behind FastAPI.
6. Add persistence for ProfileSession and related resources after the contract is stable.

This round only starts that route. It does not migrate the full Profile Setup flow, rewrite the parser, or implement job search.
