# Next Development Plan

## v4.6 Job Brief

Goal:

```text
JobSearchResult -> JobBrief
```

## Inputs

- `job_search_run_id`
- `job_result_id`
- `confirmed_profile_id`
- resume/profile context
- `use_llm`

## Outputs

- match summary
- why this job matches
- risks and gaps
- resume tailoring suggestions
- interview/project challenge questions
- application strategy

## Backend Tasks

- add JobBrief schema if missing
- add JobBrief repository/table if missing
- add usecase/service
- add API routes:
  - `POST /api/v1/job-search-runs/{run_id}/results/{result_id}/brief`
  - `GET /api/v1/job-briefs/{brief_id}`
- deterministic fallback first
- optional LLM enhancement later

## Frontend Tasks

- add Generate Brief button on job card
- add JobBrief page
- show match reasons, risks, resume advice, interview questions, strategy
- route guard from JobSearchResult to Brief

## Tests

- API tests
- repository tests
- usecase tests
- frontend build
- no real network or real LLM dependency
