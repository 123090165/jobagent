# JobImportCandidate

## Why

`JobImportCandidate` is the bridge between a saved `BriefRun` recommendation and a user-confirmed job target.

It lets us turn a ranked recommendation into a small editable candidate record before we connect it to:

- tracker
- single-job deep analysis

This round only builds the preparation layer.

## Data Flow

```text
BriefRun recommended item
  -> JobImportCandidate
  -> reviewed / ready_for_tracker / ready_for_analysis / rejected
```

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
  "user_notes": "Reviewed and ready for manual tracker import."
}
```

## Streamlit

In the `岗位批量推荐 / Job Brief` page:

1. Generate and save a brief run.
2. Click `Save as Candidate` on a recommended job.
3. Check the `Job Candidates` section.
4. Update status to:
   - `reviewed`
   - `ready_for_tracker`
   - `ready_for_analysis`
   - `rejected`

The page only shows lightweight job fields and `jd_text_preview`.

## Demo Script

```powershell
python scripts/demo_job_import_candidate.py --run-id <RUN_ID> --rank 1 --status reviewed --publish-sanitized
```

## Current Limits

- Does not auto-apply to jobs.
- Does not write into tracker yet.
- Does not trigger deep analysis yet.
- By default does not expose full `jd_text` in API or docs demo outputs.
