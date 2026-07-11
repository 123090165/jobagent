# Data And Security

## Current Data Model

Users own workflow and library data through user_id. Important tables include:

- users and auth_sessions;
- profile_sessions, resume_documents, parsed_resume_reviews, profile_drafts,
  and confirmed_profiles;
- resume_profiles;
- job_search_runs and job_search_trace_steps;
- saved_jobs and saved_job_analyses.

Saved jobs store a canonical JD snapshot separately from profile-specific
analysis snapshots. A job may be evaluated against different resume profiles
without overwriting its source data.

Local SQLite stores JSON as text so contracts can evolve without a large ORM
dependency. Public identifiers use UUID strings to remain portable.

## Authentication

Passwords use PBKDF2-SHA256 with a per-user salt. Auth sessions use random
opaque bearer tokens; only token hashes are persisted. Sessions can expire or
be revoked.

The frontend currently stores its token in localStorage and attaches it through
Axios. This is acceptable for local MVP testing but exposes the token to any
successful same-origin script injection.

The backend currently treats a missing bearer token as local-user. This is a
compatibility mode, not production authorization. Before hosted deployment:

- require authentication by default;
- enable local-user only through an explicit development setting;
- make the browser helper authenticate its backend requests;
- choose either secure HttpOnly cookies with a CSRF policy or a hardened bearer
  token lifecycle;
- add login and registration throttling and security audit events.

Frontend route guards never replace backend authorization. Every read and write
must verify resource ownership.

## Sensitive Data

Resume text, profile content, job notes, model prompts, and analysis results may
contain personal information. They are currently stored as plaintext in the
local database.

Required controls before public beta:

- explain which resume/JD content is sent to an external LLM;
- obtain user consent before external model processing;
- define retention and deletion behavior;
- support account data export and deletion;
- avoid logging raw resumes, tokens, cookies, or full prompts;
- protect database backups and production credentials;
- document the external model provider and applicable data policy.

Use HTTPS for any non-local deployment. Keep LLM and provider keys on the
server. Never send browser cookies to FastAPI.

## Untrusted Inputs

Treat all of these as untrusted:

- uploaded or pasted resume content;
- provider HTML and JSON;
- browser-visible page text;
- source URLs;
- LLM output;
- persisted JSON created by an older application version.

Enforce file and text size limits, allowlisted provider domains, schema
validation, output grounding, and deterministic quality gates. Job description
text may contain prompt-injection instructions; prompts must identify it as
evidence, never as control instructions.

## Database Evolution

init_database() currently combines table creation, additive column checks,
ownership backfill, and index creation. Do not add destructive or ambiguous
schema changes through _ensure_column.

For local MVP changes:

- make additive changes idempotent;
- record a schema migration version;
- test existing-database upgrade behavior;
- preserve user ownership and foreign-key integrity.

Before multiple deployed environments:

- adopt a migration tool and PostgreSQL;
- use reviewed forward and rollback procedures;
- separate startup health checks from schema mutation;
- add backup and restore verification.

## Concurrent Access

SQLite is not the target for high write concurrency. Current connections enable
foreign keys but do not provide a durable distributed lock or work queue.

Before supporting concurrent public users:

- move to PostgreSQL;
- use transactional writes for multi-row lifecycle changes;
- add pagination and bounded queries;
- coordinate LLM/provider concurrency globally;
- move long work to durable workers;
- recover runs left pending or running after a crash.

## Browser Extension Boundary

The browser helper may inspect BOSS authentication cookies locally and issue
user-triggered requests inside the browser session. Cookie values must not be
included in backend payloads or logs.

Request the minimum Chrome permissions required by current behavior. Any new
host permission, cookie access, or automated navigation requires a security and
product review plus updated user-facing documentation.
