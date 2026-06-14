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
- `resume_review`
- `profile_draft`
- `profile_confirmed`
- `job_search_ready`

### ResumeDocument

Uploaded or pasted resume input linked from `ProfileSession.resume_document_id`.

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
```

Planned contract routes:

```text
POST /api/v1/profile-sessions/{session_id}/resume-text
POST /api/v1/profile-sessions/{session_id}/resume-file

POST /api/v1/profile-sessions/{session_id}/parse-resume
GET  /api/v1/profile-sessions/{session_id}/parsed-review

POST  /api/v1/profile-sessions/{session_id}/profile-draft
GET   /api/v1/profile-drafts/{draft_id}
PATCH /api/v1/profile-drafts/{draft_id}
POST  /api/v1/profile-drafts/{draft_id}/confirm

POST /api/v1/job-search-runs
GET  /api/v1/job-search-runs/{run_id}

POST /api/v1/job-search-runs/{run_id}/brief
GET  /api/v1/briefs/{brief_id}
```

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
  "current_step": "resume_intake"
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

## Persistence Note

The current implementation uses an in-memory repository stub to make the contract executable and testable. Future persistence should preserve these response shapes and route paths.
