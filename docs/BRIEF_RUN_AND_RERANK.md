# BriefRun And Rerank

`BriefRun` is the minimal persistence layer for Batch Job Brief results.
It lets us save one brief result set, then rerank or filter it later without re-running search, recollection, or the full scoring pipeline.

## What It Stores

- `brief_runs`
  - `run_id`
  - `query`
  - `provider`
  - `resume_hash`
  - quality mix counters
  - timestamps
- `brief_run_items`
  - sanitized recommendation payload
  - match report JSON
  - source metadata
  - fit score and scoring quality

Safety boundary:

- We store `resume_hash`, not full `resume_text`.
- We do not persist full `jd_text` into saved recommendation JSON.
- Stored jobs keep at most `jd_text_preview` for debugging and demos.

## API

Create and save a brief run:

```http
POST /brief/runs/from-search
```

Example body:

```json
{
  "resume_text": "Python FastAPI SQL LLM ...",
  "query": "AI PyTorch Shenzhen",
  "provider": "local_db",
  "limit": 5,
  "use_llm_jd": false
}
```

Fetch a saved run:

```http
GET /brief/runs/{run_id}
```

Rerank a saved run:

```http
POST /brief/runs/{run_id}/rerank
```

Example rerank body:

```json
{
  "require_full_jd": true,
  "exclude_external_link_only": true,
  "location_keywords": ["Shenzhen"],
  "include_keywords": ["PyTorch", "biosignal"],
  "exclude_keywords": ["sales"],
  "min_fit_score": 70,
  "limit": 5
}
```

## Streamlit Demo

In the `岗位批量推荐 / Job Brief` page:

1. Generate a brief with `mock` or `local_db`.
2. Optionally check `Save this brief as a run`.
3. Copy the returned `run_id`.
4. Use the `Brief Run Rerank` section to filter and reorder the saved jobs.

The rerank action always calls the backend API and only reuses the saved `brief_run`.

## CLI Demo

Generate and save a real local brief:

```powershell
.venv\Scripts\python.exe scripts\demo_real_local_job_brief.py --resume-file data/samples/sample_resume.md --query "AI PyTorch 生理信号 深圳" --limit 5 --save-run --publish-sanitized
```

Rerank an existing run:

```powershell
.venv\Scripts\python.exe scripts\demo_brief_rerank.py --run-id <run_id> --require-full-jd --exclude-external-link-only --include-keywords PyTorch biosignal --location-keywords Shenzhen --limit 5 --publish-sanitized
```

## Current Limits

- Rerank does not call search again.
- Rerank does not recollect jobs.
- Rerank does not rerun LLM or workflow scoring.
- If the original saved run only contains weak JD snippets, rerank quality is still bounded by that source quality.
