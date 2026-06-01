# Demo Gemini Search Flow

## Purpose

`scripts/demo_gemini_search_flow.py` runs a safe end-to-end demo for the current experimental search pipeline:

1. call `POST /search/jobs` with `provider="gemini_cli"`
2. optionally try `POST /jobs/import-url`
3. build a fallback JD draft when URL import fails
4. call `POST /analyze/full`
5. write raw local outputs to `demo_runs/<timestamp>/`
6. optionally write sanitized publishable outputs to `docs/demo_runs/<timestamp>/`

This script is for local verification and demo replay. It does not change the database schema, does not trigger Streamlit UI changes, and does not automate job applications.

When Gemini returns richer JD-like content, the demo flow now prefers `item.jd_text` as the analysis input when it is present and long enough. If Gemini only returns a short summary or weak snippet, the script still falls back to the existing title/company/location/snippet/url draft.

## Prerequisites

- Gemini CLI is installed
- Gemini CLI is already logged in if you want real provider execution
- project dependencies are installed
- FastAPI is either already running, or you pass `--start-api`

## Example Command

```powershell
python scripts/demo_gemini_search_flow.py ^
  --query "腾讯 深圳 AI Agent 开发工程师 招聘" ^
  --resume-file data/samples/sample_resume.md ^
  --start-api ^
  --try-import-url ^
  --use-llm ^
  --publish-sanitized ^
  --output-dir demo_runs
```

## Defaults

- `save_result` defaults to `false`
- the script does not write to SQLite unless you explicitly pass `--save-result`
- `--api-base-url` defaults to `http://127.0.0.1:8000`
- `--timeout-seconds` defaults to `30`

## Raw Output vs Publishable Output

- `demo_runs/<timestamp>/`
  Local raw output for debugging and verification. Do not commit this directory.
- `docs/demo_runs/<timestamp>/`
  Sanitized summaries that are safe to review in GitHub. These files can be committed.
  Only a capped `jd_text` preview is published there, never the full raw `jd_text`.

## Published Search Summary

Sanitized `docs/demo_runs/<timestamp>/search_summary.json` now includes:

- `selected_is_full_jd`
- `selected_confidence`
- `selected_skills`
- `selected_jd_text_preview`

This keeps the demo reviewable in GitHub while avoiding publication of the full JD text returned by Gemini.

## Troubleshooting

- `gemini_cli disabled`
  Check `JOBAGENT_ENABLE_GEMINI_CLI=1`
- Gemini CLI not installed
  Check `JOBAGENT_GEMINI_CLI_COMMAND` or install the expected CLI
- Gemini output is not JSON
  The backend provider only accepts JSON object output with an `items` list
- Gemini returns only partial JD content
  The script records `selected_is_full_jd` and `selected_confidence`, prefers long `jd_text` when available, and otherwise falls back to the draft JD builder
- URL import failed
  The script records the import error and continues with a fallback JD draft
- `/analyze/full` failed
  Inspect `analysis_error.json` in the raw output directory

## Safety Boundaries

- does not delete files
- does not use `shell=True`
- does not execute arbitrary user commands
- only starts the fixed `uvicorn` command when `--start-api` is used
- does not pass full `resume_text` to Gemini CLI
- does not publish full `jd_text` into `docs/demo_runs/`
- does not auto-apply to jobs
- does not bypass anti-bot protections
- does not auto-save to SQLite by default
- only commits sanitized summaries to GitHub
