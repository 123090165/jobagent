# Application Tracker

`ApplicationRecord` is the minimal tracker layer for jobs that the user actually wants to follow.

The tracker is intentionally narrow:

- it records local application status
- it does not auto-apply
- it does not log into job sites
- it does not manage reminders or calendars yet

## Data Flow

The tracker now supports two entry paths:

```text
job_posting -> application_record
```

and

```text
SearchResultItem / BriefRun item
  -> JobImportCandidate
  -> ApplicationRecord
```

The second path is useful when a recommendation comes from search or brief generation first, and only later becomes a real target job for tracking.

## Statuses

Current application statuses:

- `interested`
- `applied`
- `interviewing`
- `rejected`
- `offer`
- `archived`

## Stored Fields

Each tracker record includes:

- `job_id`
- `status`
- `notes`
- `next_action`
- `resume_version_id`
- `resume_version_label`
- `created_at`
- `updated_at`

One `job_posting` keeps one tracker record. Saving the same `job_id` again updates the existing record instead of creating a duplicate.

## APIs

Create or update directly from a job posting:

```http
POST /applications
```

Example:

```json
{
  "job_id": 1,
  "status": "interested",
  "notes": "Good fit for backend and AI platform work.",
  "next_action": "Tailor resume",
  "resume_version_id": 1,
  "resume_version_label": "v1-fastapi-backend"
}
```

Create from a confirmed candidate:

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

List and detail:

```text
GET /applications
GET /applications?status=applied
GET /applications?keyword=FastAPI
GET /applications/{application_id}
```

Update:

```http
PATCH /applications/{application_id}
```

## Notes

- `JobImportCandidate` is the review layer, not the tracker itself.
- The candidate import endpoint creates a minimal `job_postings` record when the job only exists in brief results.
- The tracker remains local and deterministic; it does not invoke LLM-only logic or any auto-apply flow.
