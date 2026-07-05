# Database, Auth, and User Library Plan

## Goal

Add real user-owned persistence around the current v4 flow:

```text
User account
-> resume profile library
-> job search / browser capture
-> saved job library with structured JD and analysis
```

This plan focuses on data ownership, storage shape, and implementation order. It
does not change the current non-goals around auto-apply, CAPTCHA handling, or
browser automation.

## Phase 1 Implementation Status

Implemented:

- `users` and `auth_sessions` with username/password login.
- Opaque bearer tokens stored as server-side token hashes.
- `user_id` ownership columns for current ProfileSession-rooted tables.
- Local compatibility fallback through the generated `local` user when no
  bearer token is provided.
- Resume profile library APIs under `/api/v1/resume-profiles`.
- Saved job library APIs under `/api/v1/saved-jobs`.
- Confirmed profiles are copied into `resume_profiles`.
- Search results can be promoted into `saved_jobs` with analysis snapshots.

Still pending:

- frontend login/register pages and route guard;
- frontend resume profile library page;
- frontend saved job library page and save buttons;
- production-grade auth choices such as HttpOnly cookies, CSRF policy, and
  hosted deployment hardening.

## Current State

The project already has local SQLite persistence through
`app/storage/database.py` and repository classes under `app/repositories`.
Current ProfileSession data is persisted in tables such as:

- `profile_sessions`
- `resume_documents`
- `parsed_resume_reviews`
- `profile_drafts`
- `confirmed_profiles`
- `job_search_runs`
- `job_search_trace_steps`

The important gaps are:

- no `users` table;
- no password login or current-user dependency;
- no `user_id` ownership on ProfileSession resources;
- no durable resume profile library independent of a single workflow session;
- no durable saved-job/bookmark table;
- job search results are stored only as JSON snapshots inside
  `job_search_runs.results_json`.

## Technology Choice

### Phase 1: Local MVP

Use the existing stack:

- database: SQLite via Python standard-library `sqlite3`;
- database path: existing `JOBAGENT_DB_PATH`, defaulting to
  `data/jobagent.sqlite3`;
- backend framework: FastAPI;
- schema contracts: Pydantic v2;
- persistence boundary: existing repository pattern;
- frontend auth state: Vue + Pinia + Axios authorization header.

Rationale:

- The project is currently a local-first FastAPI/Vue app with light
  dependencies.
- Existing tables and tests already assume SQLite and `init_database`.
- SQLite is enough for one-machine development and early product validation.
- Avoiding SQLAlchemy/Alembic in this step keeps the change focused on product
  data modeling instead of an ORM migration.

### Auth Token Choice

Use opaque bearer tokens for the MVP:

- login returns a random token generated with `secrets.token_urlsafe`;
- store only `sha256(token)` in `auth_sessions`;
- clients send `Authorization: Bearer <token>`;
- backend resolves the token through a FastAPI dependency.

Password storage:

- never store plaintext passwords;
- store per-user salt and password hash;
- use `hashlib.pbkdf2_hmac("sha256", ...)` or `hashlib.scrypt` from the Python
  standard library;
- compare hashes with `hmac.compare_digest`.

This avoids adding a JWT dependency now. If the app becomes hosted or
multi-device, revisit HttpOnly secure cookies, CSRF policy, token rotation, and
possibly OAuth.

### Migration Choice

For this phase, keep idempotent schema creation in `init_database`, but add a
small migration ledger:

```text
schema_migrations(version, name, applied_at)
```

Use explicit migration functions for ownership backfills and table creation.
Continue to use `_ensure_column` only for simple additive columns.

Move to SQLAlchemy + Alembic only when one of these becomes true:

- multiple deployed environments need repeatable migrations;
- the schema starts changing frequently;
- PostgreSQL becomes the production target;
- repository SQL becomes difficult to review manually.

### Future Production Target

Keep the schema compatible with PostgreSQL:

- use UUID strings as public IDs;
- avoid SQLite-specific query behavior where practical;
- keep JSON payloads in `*_json` text columns for now, with the option to map
  them to PostgreSQL `jsonb` later;
- keep timestamps as ISO-8601 UTC strings in the current style, or migrate all
  at once later.

## Data Model

### Users

Purpose: login identity and owner of all private data.

```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_algorithm TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    disabled_at TEXT
);
```

Notes:

- `username` is enough for the requested login model.
- Email can be added later; do not overload username as email unless product
  requirements say so.
- `disabled_at` lets us block login without deleting owned data.

### Auth Sessions

Purpose: server-side login sessions.

```sql
CREATE TABLE auth_sessions (
    auth_session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    user_agent TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

Rules:

- token lookup must ignore expired or revoked sessions;
- logout sets `revoked_at`;
- password change should revoke all existing sessions for the user.

### User Ownership Columns

Add `user_id` to session-rooted tables:

- `profile_sessions`
- `resume_documents`
- `parsed_resume_reviews`
- `profile_drafts`
- `confirmed_profiles`
- `job_search_runs`

The root ownership check should happen at `profile_sessions`. Add direct
`user_id` columns to derived tables anyway so repositories can enforce ownership
without always joining through the session.

Backfill existing local data to a generated local user:

```text
username: local
display_name: Local User
```

This preserves current development data and avoids breaking existing smoke
flows.

### Resume Profile Library

Purpose: stable user-owned library of confirmed resume profiles, independent of
the transient workflow step that produced them.

```sql
CREATE TABLE resume_profiles (
    resume_profile_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_session_id TEXT,
    source_confirmed_profile_id TEXT,
    name TEXT NOT NULL,
    summary TEXT NOT NULL,
    target_roles_json TEXT NOT NULL,
    target_directions_json TEXT NOT NULL,
    core_skills_json TEXT NOT NULL,
    supporting_skills_json TEXT NOT NULL,
    search_keywords_json TEXT NOT NULL,
    preferred_locations_json TEXT NOT NULL,
    work_arrangements_json TEXT NOT NULL,
    strengths_json TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    raw_resume_text TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (source_session_id) REFERENCES profile_sessions(session_id),
    FOREIGN KEY (source_confirmed_profile_id)
        REFERENCES confirmed_profiles(confirmed_profile_id)
);
```

Rules:

- confirming a profile creates or updates a `resume_profiles` item;
- users can rename, archive, and choose a default profile;
- job search should use a selected `resume_profile_id` when available;
- keep `profile_json` as the full snapshot so future UI changes do not lose
  information.

### Saved Job Library

Purpose: user-owned collection of jobs with structured JD data.

```sql
CREATE TABLE saved_jobs (
    saved_job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_provider TEXT,
    source_url TEXT,
    normalized_source_key TEXT,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    salary TEXT,
    employment_type TEXT,
    raw_jd_text TEXT NOT NULL,
    structured_jd_json TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'saved',
    notes TEXT,
    first_seen_at TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

Recommended `status` values:

- `saved`
- `interested`
- `applied`
- `rejected`
- `archived`

Deduplication:

- if `source_url` exists, use `(user_id, source_url)` as the main upsert key;
- otherwise use `(user_id, normalized_source_key)`;
- `normalized_source_key` can be built from normalized title, company, location,
  and source provider.

### Saved Job Analyses

Purpose: store profile-specific analysis separately from the saved job itself.
A job can be analyzed against different resume profiles over time.

```sql
CREATE TABLE saved_job_analyses (
    saved_job_analysis_id TEXT PRIMARY KEY,
    saved_job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    resume_profile_id TEXT,
    source_job_search_run_id TEXT,
    source_job_result_id TEXT,
    match_score INTEGER,
    confidence_label TEXT,
    recommendation TEXT,
    matched_strengths_json TEXT NOT NULL DEFAULT '[]',
    critical_gaps_json TEXT NOT NULL DEFAULT '[]',
    resume_actions_json TEXT NOT NULL DEFAULT '[]',
    interview_questions_json TEXT NOT NULL DEFAULT '[]',
    analysis_json TEXT NOT NULL,
    analysis_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (saved_job_id) REFERENCES saved_jobs(saved_job_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (resume_profile_id) REFERENCES resume_profiles(resume_profile_id),
    FOREIGN KEY (source_job_search_run_id)
        REFERENCES job_search_runs(job_search_run_id)
);
```

Rules:

- `saved_jobs` stores the canonical JD snapshot;
- `saved_job_analyses` stores match/fit analysis snapshots;
- the saved-job detail API can return the latest analysis by default and a
  history list when needed.

## Backend API Plan

### Auth

Add `app/api/v1/auth.py`:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Add:

- `app/schemas/auth.py`
- `app/repositories/user_repository.py`
- `app/repositories/auth_session_repository.py`
- `app/services/password_service.py`
- `app/application/auth_usecases.py`
- `app/api/dependencies.py` with `get_current_user`

### Profile Sessions

Change create-session flow:

```text
POST /api/v1/profile-sessions
Authorization: Bearer <token>
```

The backend should attach `user_id` from the token. Every session read/write
must verify the current user owns the session.

### Resume Profile Library

Add `app/api/v1/resume_profiles.py`:

- `GET /api/v1/resume-profiles`
- `GET /api/v1/resume-profiles/{resume_profile_id}`
- `PATCH /api/v1/resume-profiles/{resume_profile_id}`
- `POST /api/v1/resume-profiles/{resume_profile_id}/default`
- `POST /api/v1/resume-profiles/{resume_profile_id}/archive`

When `POST /api/v1/profile-drafts/{profile_draft_id}/confirm` or the existing
confirmation path creates `confirmed_profiles`, also create/update a
`resume_profiles` row.

### Saved Jobs

Add `app/api/v1/saved_jobs.py`:

- `GET /api/v1/saved-jobs`
- `POST /api/v1/saved-jobs`
- `GET /api/v1/saved-jobs/{saved_job_id}`
- `PATCH /api/v1/saved-jobs/{saved_job_id}`
- `POST /api/v1/saved-jobs/{saved_job_id}/archive`
- `POST /api/v1/saved-jobs/from-search-result`
- `POST /api/v1/saved-jobs/from-browser-capture`

The `from-search-result` endpoint should promote one `JobSearchResult` snapshot
from `job_search_runs.results_json` into `saved_jobs` plus
`saved_job_analyses`.

The browser capture analysis path should optionally save the captured JD and
analysis directly to the library.

## Frontend Plan

Add:

- auth pages: login/register;
- Pinia auth store;
- Axios interceptor that attaches `Authorization`;
- route guard for all product routes after login;
- resume profile library page;
- saved job library page;
- save button on job search results;
- saved indicator and status selector on job detail/analysis views.

Keep the first version utilitarian:

- username/password form;
- current user menu/logout;
- list/detail pages for profile library and saved jobs;
- no social login;
- no team/workspace model.

## Implementation Order

1. Add database migrations for `users`, `auth_sessions`, ownership columns,
   `resume_profiles`, `saved_jobs`, and `saved_job_analyses`.
2. Backfill existing rows to a generated local user.
3. Implement password hashing and auth session repositories.
4. Add auth schemas, use cases, and API routes.
5. Add `get_current_user` and protect new library routes.
6. Add ownership checks to ProfileSession APIs.
7. Create resume profile library from confirmed profiles.
8. Add saved job repository and APIs.
9. Add frontend login state and auth route guard.
10. Add profile library UI and saved job library UI.
11. Add save actions from search results and browser capture.
12. Expand tests around auth, ownership, and persistence.

## Test Plan

Backend tests:

- password hash never equals plaintext;
- valid login returns a token;
- invalid login fails with a generic error;
- revoked/expired token cannot access protected routes;
- user cannot read another user's profile session;
- confirming a profile creates a `resume_profiles` row;
- saving the same source URL twice upserts or returns the existing saved job;
- saved job analysis is linked to the selected resume profile;
- existing local data is backfilled to the local user.

Frontend tests:

- logged-out users are redirected to login;
- login stores auth state and attaches the bearer token;
- logout clears auth state;
- saved-job button calls the correct API and updates UI state.

## Open Decisions

- Whether registration should be open in the UI or only enabled for local/dev.
- Whether the initial local user should be auto-created with a configured
  password or created through first-run registration.
- Whether raw resume text should remain in `resume_profiles` long term, or be
  replaced by a separate document table with stricter privacy controls.
- Whether saved jobs should support multiple folders/lists in addition to tags
  and status.

## Acceptance Criteria

The step is done when:

- a user can register/login/logout with username and password;
- profile sessions and all derived data are owned by a user;
- a confirmed resume can be found later in the user's resume profile library;
- a search result or browser-captured JD can be saved to the user's job library;
- saved jobs store structured JD data and at least one analysis snapshot;
- tests prove cross-user access is blocked;
- existing local development data still works after migration/backfill.
