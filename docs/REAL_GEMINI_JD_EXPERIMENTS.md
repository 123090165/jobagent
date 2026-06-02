# Real Gemini JD Experiments

## Purpose

`scripts/run_real_gemini_jd_experiments.py` is a batch experiment runner for the current Gemini search pipeline.

It does not call Gemini CLI directly. Instead, it reuses the existing safe demo entry:

- `scripts/demo_gemini_search_flow.py`

The goal is to run multiple real job-search queries, collect the sanitized outputs from `docs/demo_runs/<timestamp>/`, and generate a higher-level experiment summary for review.

## Preconditions

Before using this script:

- Gemini CLI is installed
- Gemini CLI is already logged in
- Python dependencies are installed
- `JOBAGENT_ENABLE_GEMINI_CLI=1` is configured for the API process
- you have a sanitized local resume sample such as `data/samples/sample_resume.md`

## Example Command

```powershell
python scripts/run_real_gemini_jd_experiments.py ^
  --resume-file data/samples/sample_resume.md ^
  --start-api ^
  --try-import-url ^
  --query "腾讯 深圳 AI Agent 开发工程师 招聘" ^
  --query "Tencent Shenzhen LLM application engineer job posting"
```

If you do not pass any `--query` or `--query-file`, the runner falls back to three default queries and still respects `--max-runs`.

## Output Files

Per-run sanitized outputs still come from:

- `docs/demo_runs/<timestamp>/`

The batch runner additionally writes:

- `docs/demo_runs/REAL_GEMINI_JD_EXPERIMENT_SUMMARY.md`
- `docs/demo_runs/real_gemini_jd_experiment_summary.json`

## Classification

Each run is classified as one of:

- `GOOD`
  - `analysis_succeeded = true`
  - `selected_url` is non-empty
  - `selected_confidence >= 0.7`
  - `selected_is_full_jd = true`
- `PARTIAL`
  - analysis succeeded, but the result still depends on fallback JD, or `is_full_jd = false`, or confidence is below `0.7`
- `FAILED`
  - search failed, or analyze failed, or no selected item was returned

## What The Summary Helps Judge

The aggregate report is meant to help answer:

- Can Gemini CLI stably find job-like URLs?
- Can Gemini CLI stably return full JD-like content?
- How often does URL import succeed?
- Do we need a follow-up `JD Acquisition Quality Upgrade` phase?

## Safety Boundaries

- does not delete files
- does not use `shell=True`
- does not execute arbitrary user input as commands
- does not call Gemini CLI directly
- only invokes `scripts/demo_gemini_search_flow.py`
- gives each child process a timeout
- defaults `max-runs` to `5`
- does not upload full resume text
- does not publish full JD text
- does not publish raw Gemini CLI output
- does not write SQLite unless a future version explicitly changes scope
- does not auto-commit or auto-push
