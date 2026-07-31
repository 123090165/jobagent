# API Contract V1

/api/v1 is the product API used by web/ and the browser helper. FastAPI OpenAPI
at /docs is the field-level source of truth; this document defines resource
groups and behavioral expectations.

## Authentication

~~~text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
~~~

Login returns an opaque bearer token. The server stores only its hash. Resource
routes resolve a current user and repositories scope data by user_id.

Current compatibility behavior: a request without credentials resolves to the
generated local-user. This supports local development and the current Side
Panel. It must become an explicit development mode before hosted deployment.

## Profile Workflow

~~~text
POST /api/v1/profile-sessions
GET  /api/v1/profile-sessions/{session_id}
POST /api/v1/profile-sessions/{session_id}/resume-text
POST /api/v1/profile-sessions/{session_id}/resume-file
GET  /api/v1/profile-sessions/{session_id}/resume
POST /api/v1/profile-sessions/{session_id}/parse-resume
GET  /api/v1/profile-sessions/{session_id}/parsed-review
POST /api/v1/profile-sessions/{session_id}/profile-draft
GET  /api/v1/profile-drafts/{draft_id}
PATCH /api/v1/profile-drafts/{draft_id}
POST /api/v1/profile-drafts/{draft_id}/confirm
GET  /api/v1/confirmed-profiles/{confirmed_profile_id}
~~~

Resume parsing supports explicit regeneration and optional LLM analysis.
Profile draft creation supports explicit regeneration.

Resume file intake accepts UTF-8 `.txt` and `.md`, text-layer `.pdf`, and
Open XML `.docx` files. PDF text is extracted with PyMuPDF; DOCX paragraphs and
tables are extracted with python-docx. All formats produce the same persisted
plain-text ResumeDocument and continue through the existing deterministic or
LLM-assisted parse endpoint. Scanned PDFs without a text layer require OCR and
are rejected by the current intake boundary.

`JOBAGENT_MAX_RESUME_FILE_BYTES` controls the upload limit and defaults to 5 MB.
PDFs are limited to 50 pages. DOCX archives are checked for bounded entry count
and uncompressed size before parsing.

## Resume Profile Library

~~~text
GET  /api/v1/resume-profiles
GET  /api/v1/resume-profiles/{profile_id}
PATCH /api/v1/resume-profiles/{profile_id}
POST /api/v1/resume-profiles/{profile_id}/default
POST /api/v1/resume-profiles/{profile_id}/archive
POST /api/v1/resume-profiles/{profile_id}/restore
DELETE /api/v1/resume-profiles/{profile_id}
~~~

A confirmed profile is promoted to a durable user-owned resume profile.
Deleting a library profile does not delete its source session, search runs, or
saved jobs. Profile references in analysis and origin records are detached;
their profile-label and search-query snapshots remain available for audit.

## Job Search

~~~text
GET  /api/v1/profile-sessions/{session_id}/search-mission
PUT  /api/v1/profile-sessions/{session_id}/search-mission
POST /api/v1/profile-sessions/{session_id}/search-mission/interpret
POST /api/v1/profile-sessions/{session_id}/search-mission/confirm
POST /api/v1/job-search-runs/preview
POST /api/v1/job-search-runs
POST /api/v1/job-search-runs/browser-helper
GET  /api/v1/job-search-runs
GET  /api/v1/job-search-runs/{run_id}
DELETE /api/v1/job-search-runs/{run_id}
GET  /api/v1/job-search-runs/{run_id}/steps
GET  /api/v1/job-search-runs/{run_id}/feedback
POST /api/v1/job-search-runs/{run_id}/results/{result_id}/feedback
GET  /api/v1/profile-sessions/{session_id}/job-search-runs
~~~

Run creation persists a pending run and schedules execution. Clients poll run
and step endpoints until completion or failure.

The collection GET lists recent runs across the current user's profile
sessions. The session-scoped GET remains available for workflow-local history.
Deleting a run retains saved jobs and their analysis snapshots while detaching
the source-run reference.

analysis_mode decides deterministic versus LLM-assisted behavior. llm_provider
selects the implementation behind the shared LLM interface. Provider selection
is independent from model selection.

## Saved Job Library

~~~text
GET   /api/v1/saved-jobs
POST  /api/v1/saved-jobs
POST  /api/v1/saved-jobs/from-search-result
POST  /api/v1/saved-jobs/from-browser-capture
GET   /api/v1/saved-jobs/{saved_job_id}
DELETE /api/v1/saved-jobs/{saved_job_id}
GET   /api/v1/saved-jobs/{saved_job_id}/analyses
GET   /api/v1/saved-jobs/{saved_job_id}/contexts
GET   /api/v1/saved-jobs/{saved_job_id}/status-history
GET   /api/v1/saved-jobs/{saved_job_id}/briefs
POST  /api/v1/saved-jobs/{saved_job_id}/briefs
GET   /api/v1/saved-jobs/{saved_job_id}/preparation
POST  /api/v1/saved-jobs/{saved_job_id}/preparation
PUT   /api/v1/saved-jobs/{saved_job_id}/preparation/answers
GET   /api/v1/saved-jobs/{saved_job_id}/preparation/prompt.txt
PATCH /api/v1/saved-jobs/{saved_job_id}
POST  /api/v1/saved-jobs/{saved_job_id}/archive
~~~

Preparation answers use a required structured `experience_level` and optional
free-text `detail`. The request action is `save`, `complete`, or `stop`. Saving
checkpoints a paused session, completing generates recommendations and any
needed learning resources, and stopping intentionally produces no summary.

Deleting a saved job removes only that job's analysis and status history. It
does not delete search runs or resume profiles.

Saving a result copies a canonical JD snapshot and a profile-specific analysis
snapshot. It also records a durable context linking the saved job to its resume
profile, search run, result, and analysis. Re-saving the same normalized source
reuses the user-owned saved job while preserving distinct profile/search
contexts.

## Browser And Status

~~~text
POST /api/v1/browser/job-captures
POST /api/v1/browser/job-captures/{capture_id}/analyze
POST /api/v1/browser/job-captures/analyze  # compatibility: capture + analyze
GET  /api/v1/job-search-providers/status
GET  /api/v1/llm/status
GET  /health
~~~

Status endpoints expose configuration state, never secrets.

## Career Assistant

~~~text
POST   /api/v1/chat/conversations
POST   /api/v1/browser-helper/sessions
GET    /api/v1/browser-helper/context-catalog
GET    /api/v1/chat/context-catalog
GET    /api/v1/chat/conversations
GET    /api/v1/chat/conversations/{conversation_id}
PATCH  /api/v1/chat/conversations/{conversation_id}
GET    /api/v1/chat/conversations/{conversation_id}/memory
GET    /api/v1/chat/conversations/{conversation_id}/turns
POST   /api/v1/chat/conversations/{conversation_id}/turns
POST   /api/v1/chat/conversations/{conversation_id}/context/search-results
DELETE /api/v1/chat/conversations/{conversation_id}/context/search-results/{run_id}/{result_id}
DELETE /api/v1/chat/conversations/{conversation_id}/turns/{turn_id}
DELETE /api/v1/chat/conversations/{conversation_id}/memory
DELETE /api/v1/chat/conversations/{conversation_id}
~~~

Browser Helper session issuance requires a valid full bearer session; anonymous
local-user compatibility and an existing `browser_helper` token are rejected.
The returned token expires after eight hours and is limited to current-page
capture plus the documented Assistant subset.

`POST /api/v1/chat/conversations/{conversation_id}/context/browser-captures`
adds an owned browser capture ID to the conversation's bounded data scope. It
does not copy JD text into the conversation row. The full JD remains in the
capture resource and is re-read under the current user's authorization when a
question requires search-result context.

Conversations persist a bounded data-access policy (`auto`, `always`, or
`off`). A turn uses a client-generated idempotency key. The answer agent may
request only fixed read-only tool names, while application code converts those
requests into source categories and performs every resource lookup with the
current user's ID. Returned citations are resolved from the server evidence
packet rather than accepted from model-provided metadata.

Completed turns include a bounded `retrieval_plan`. `agent_sources` records the
sources actually selected by agent tools and deterministic policy, while
`requests` records the policy-approved source and one of `use_attachment`, `reuse_previous`,
`use_pinned`, or `load_recent`. A turn may include up to five owned search-result,
browser-capture, or Saved Job references in `context_attachments`. Search-result
and browser-capture references can be retained by their dedicated context
endpoints; only identifiers are stored in the conversation scope. `reuse_previous`
reuses only the prior resource selector; the
repository still reads the current owned record. `freshness=refresh_required`
forbids treating prior answer text or evidence content as a current snapshot.
The plan contains no database query, user identity, business resource body, or
model answer instruction.

Completed turns persist their original `context_attachments`. A retry creates a
new turn with `retry_of_turn_id`; the backend ignores replacement question or
rejects replacement attachment selectors, then reuses the owned source turn's
original question and attachments. Historical turns created before this field
existed retry without
attachments. Model failures expose only bounded categories such as
`network_error`, `timeout`, `authentication_failed`, `rate_limited`,
`model_unavailable`, or `invalid_response`, never raw provider responses or
credentials.

The memory status endpoint is an owned, read-only projection. It reports
completed/recent turn counts, the current summary boundary and version, pinned
resource references, and references used by the latest completed answer.
Business resource bodies are not copied into this projection. Resource labels
and availability are resolved under the current user's permissions when the
response is built.

The context catalog returns lightweight, current-user-owned Profile, completed
Search Run, and active Saved Job options. A conversation may pin whole search
runs or individual `(job_search_run_id, job_result_id)` pairs. Pinned IDs remain
advisory context and are re-authorized on every read.

Deleting a turn deletes its question, answer, route, and citations and
invalidates derived memory. Clearing memory keeps the conversation resource but
removes all turns and derived state. Deleting a conversation physically removes
its local chat rows.

## Errors

Known application errors use:

~~~json
{
  "detail": "Human readable message",
  "error_code": "machine_readable_code"
}
~~~

Use detail for recovery text and error_code for routing or state logic.
Framework request-validation errors may retain FastAPI's default shape.

Ownership failures should not reveal whether another user's resource exists.
After a state error, clients reload the owning ProfileSession before routing.

## Contract Change Rules

- Add Pydantic types before changing frontend clients.
- Keep provider payloads behind normalized candidate contracts.
- Preserve fields when adding optional diagnostics.
- During local baseline development, recreate cleared SQLite data after persisted
  contract changes; introduce versioned migrations before deployed data must be
  preserved.
- Update this document and focused API tests in the same change.
