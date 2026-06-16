# API Contract V1

## Boundary

`/api/v1` is the contract between the FastAPI backend in `app/` and the Vue 3 frontend in `web/`.

The frontend must not import backend services directly. All user-facing product flows should call `/api/v1`.

## Resources

### ProfileSession

Primary workflow resource for one resume-to-search-ready-profile flow.

Fields:

- `session_id`
- `status`
- `created_at`
- `updated_at`
- `resume_document_id`
- `parsed_review_id`
- `profile_draft_id`
- `confirmed_profile_id`
- `current_step`

Allowed `status` values:

- `active`
- `completed`
- `archived`

Allowed `current_step` values:

- `resume_intake`
- `created`
- `resume_empty`
- `resume_ready`
- `resume_review`
- `profile_draft`
- `profile_confirmed`
- `job_search_ready`
- `job_search_running`
- `job_search_completed`
- `brief_ready`
- `archived`

`resume_intake` is the v4.0 skeleton value. New v4.1+ work should prefer the hardened state machine in `docs/V4_STATE_MACHINE.md`.

### ResumeDocument

Uploaded or pasted resume input linked from `ProfileSession.resume_document_id`.

Starting in v4.1, `ProfileSession` and `ResumeDocument` must be persisted and recoverable. The v4.0 in-memory repository is only acceptable for the skeleton and tests.

### ParsedResumeReview

Structured review output produced from a resume document and linked from `ProfileSession.parsed_review_id`.

### ProfileDraft

Editable profile generated from parsed resume review and linked from `ProfileSession.profile_draft_id`.

### ConfirmedProfile

Search-ready profile confirmed by the user and linked from `ProfileSession.confirmed_profile_id`.

### JobSearchRun

A search run created from a confirmed profile.

### JobBrief

A brief generated for a job search result.

## Resource Relationship

```text
ProfileSession
  -> ResumeDocument
  -> ParsedResumeReview
  -> ProfileDraft
  -> ConfirmedProfile
  -> JobSearchRun
  -> JobBrief
```

## Routes

Implemented in this skeleton:

```text
POST /api/v1/profile-sessions
GET  /api/v1/profile-sessions/{session_id}
POST /api/v1/profile-sessions/{session_id}/resume-text
POST /api/v1/profile-sessions/{session_id}/resume-file
GET  /api/v1/profile-sessions/{session_id}/resume
POST /api/v1/profile-sessions/{session_id}/parse-resume
GET  /api/v1/profile-sessions/{session_id}/parsed-review
```

Planned contract routes:

```text
POST /api/v1/profile-sessions/{session_id}/resume-text
POST /api/v1/profile-sessions/{session_id}/resume-file

POST /api/v1/profile-sessions/{session_id}/parse-resume
POST /api/v1/profile-sessions/{session_id}/parse-resume?regenerate=true
GET  /api/v1/profile-sessions/{session_id}/parsed-review

POST  /api/v1/profile-sessions/{session_id}/profile-draft
POST  /api/v1/profile-sessions/{session_id}/profile-draft?regenerate=true
GET   /api/v1/profile-drafts/{draft_id}
PATCH /api/v1/profile-drafts/{draft_id}
POST  /api/v1/profile-drafts/{draft_id}/confirm

POST /api/v1/job-search-runs
GET  /api/v1/job-search-runs/{run_id}

POST /api/v1/job-search-runs/{run_id}/brief
POST /api/v1/job-search-runs/{run_id}/brief?regenerate=true
GET  /api/v1/briefs/{brief_id}
```

Generation endpoints are idempotent by default. If a current result already exists, return it unless `regenerate=true` is explicitly requested.

## Current Response Examples

`POST /api/v1/profile-sessions`

```json
{
  "session_id": "uuid",
  "status": "active",
  "created_at": "2026-06-14T00:00:00Z",
  "updated_at": "2026-06-14T00:00:00Z",
  "resume_document_id": null,
  "parsed_review_id": null,
  "profile_draft_id": null,
  "confirmed_profile_id": null,
  "current_step": "created"
}
```

`GET /api/v1/profile-sessions/{session_id}` returns the same `ProfileSession` resource.

Unknown sessions return:

```json
{
  "detail": "Profile session not found.",
  "error_code": "profile_session_not_found"
}
```

`GET /api/v1/profile-sessions/{session_id}/resume` returns the current `ResumeDocument` resource for that session.

If the session exists but no current resume has been stored yet, the endpoint returns:

```json
{
  "detail": "Resume document not found for this session.",
  "error_code": "resume_document_not_found"
}
```

## Persistence Note

The current implementation uses an in-memory repository stub to make the v4.0 contract executable and testable. Starting in v4.1, user workflow resources must be persisted. Future persistence should preserve these response shapes and route paths.

## Error Contract

All product-flow `/api/v1` errors should use:

```json
{
  "detail": "Human readable error message",
  "error_code": "machine_readable_error_code"
}
```

Recommended error codes and frontend handling rules are defined in `docs/V4_ERROR_CONTRACT.md`.
