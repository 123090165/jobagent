# JobImportCandidate

## Why

`JobImportCandidate` is the bridge between a saved `BriefRun` recommendation and a user-confirmed job target.

It gives us one lightweight, editable record before we decide to:

- push the job into the application tracker
- trigger later single-job analysis work

## Data Flow

```text
SearchResultItem / BriefRun item
  -> JobImportCandidate
  -> reviewed / ready_for_tracker / ready_for_analysis / imported / rejected
  -> ApplicationRecord
```

`SearchResultItem` and `BriefRun` recommendations are ranking outputs. They are not tracker records.
`JobImportCandidate` is the confirmation layer where the user can review fields, keep notes, and decide whether the job should enter the tracker.

## API

Create from a saved brief run:

```http
POST /job-candidates/from-brief-run
```

Example:

```json
{
  "run_id": "abc123run",
  "rank": 1
}
```

Get one candidate:

```http
GET /job-candidates/{candidate_id}
```

Optional query:

```text
include_full_jd=true
```

By default, the API does not return full `jd_text`.

List candidates:

```http
GET /job-candidates?status=reviewed&limit=20
```

Patch candidate:

```http
PATCH /job-candidates/{candidate_id}
```

Example:

```json
{
  "status": "ready_for_tracker",
  "user_notes": "Reviewed and ready for tracker import."
}
```

Create an application record from a confirmed candidate:

```http
POST /job-candidates/{candidate_id}/create-application
```

Example:

```json
{
  "status": "interested",
  "notes": "Import candidate into tracker",
  "next_action": "Tailor resume"
}
```

This endpoint:

1. creates a minimal `job_postings` entry from the candidate if needed
2. creates or reuses an `ApplicationRecord`
3. marks the candidate as `imported`

Repeated calls are idempotent for the same candidate and return the existing tracker record instead of creating duplicates.

## Current Limits

- Does not auto-apply to jobs.
- Does not trigger deep analysis automatically.
- Does not add a complex state machine around candidate import.
- By default does not expose full `jd_text` in API or sanitized demo outputs.
