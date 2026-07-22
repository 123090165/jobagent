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
- replace local compatibility fallback with mandatory authentication on every route;
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

Resume uploads accept only allowlisted extensions. PDF parsing is bounded by
file size and page count. DOCX parsing is bounded by compressed upload size,
archive entry count, and total uncompressed size. Extracted document text is
untrusted input and receives the same validation and LLM prompt boundary as
pasted resume text.

Interview learning-resource MCP calls send only a bounded skill-topic search
query, not the resume, JD, profile, user answers, or authentication data. The
MCP endpoint is backend configuration and must use a trusted HTTP(S) server.
Returned URLs are treated as untrusted external links and restricted to HTTP(S).
Exporting an external-model prompt is an explicit user action because that file
contains selected JD and profile context.

Chat builds a metadata-only manifest from the owned conversation before the
answer agent decides whether read-only tools are needed. The manifest exposes
source types, labels, and statuses, not database selectors or raw resource
bodies. Fixed application functions enforce source allowlists,
conversation scope, tool-call limits, evidence budgets, and current `user_id`
ownership. Chat has no business-data write tools.

A non-career or ambiguous question receives no personal business context by
default. Hard refusal is reserved for prohibited capabilities such as
cross-user access, secret extraction, raw SQL or system command execution. If
business-data mutation tools are added later, the LLM may only propose a typed
operation; a user-bound backend confirmation must occur before execution, and
repository ownership checks remain mandatory.

Agent tool output never contains an executable database query or user selector.
The resolver can reference only explicit owned attachments, the current
conversation's pinned IDs, recent owned resources, or citation IDs previously
persisted in that same owned conversation. A refresh request may retain those
IDs as selectors, but current content is fetched again through user-scoped
repositories; cached evidence or prior answer text is not treated as refreshed
business data.

Retry lineage is resolved under both the authenticated `user_id` and current
conversation ID. A retry cannot override the source turn's question or
attachments; every reused selector is authorized again before retrieval. Raw
provider exception text is not returned to clients. Fallback diagnostics are
reduced to bounded operational categories such as network, timeout,
authentication, rate-limit, model-unavailable, or invalid-response.

Chat prompt and output content remains redacted from Langfuse even when global
content capture is enabled. This keeps local memory deletion meaningful without
requiring third-party trace deletion. Raw resume text is excluded from chat
evidence by default. Job descriptions, saved notes, old turns, summaries, and
model output are all untrusted input and cannot act as system instructions.

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

Assistant pairing issues a separate eight-hour `browser_helper` bearer session.
Issuance requires an authenticated full session and does not use anonymous
local-user compatibility.
The extension stores it in `chrome.storage.session`; it is accepted only by the
Chat create/list/read-turn/send-turn/pin subset and current-page capture. It
cannot delete Chat memory or authorize ordinary profile, saved-job, or account
APIs. Backend resource reads still require the scoped session's `user_id`.

The dedicated Browser Helper catalog is intentionally metadata-only: Saved Job
ID, title, company, and status. It never returns raw JD text, notes, tags, or
analysis. A selected ID is treated as an untrusted reference and ownership is
checked again when the Chat turn is created.

Current-page JD capture stores one backend-owned record and returns only a
`capture_id` plus a bounded preview. The extension does not persist JD text.
Chat and optional match analysis resolve that capture under the scoped session's
`user_id`; a capture ID owned by another user is treated as unavailable.

Request the minimum Chrome permissions required by current behavior. Any new
host permission, cookie access, or automated navigation requires a security and
product review plus updated user-facing documentation.
