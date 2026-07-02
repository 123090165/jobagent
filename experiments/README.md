# Resume Extraction Comparison Experiment

This directory contains local-only experiments for comparing DeepSeek-based resume extraction strategies. It does not modify production parser behavior, API routes, frontend behavior, repositories, or job brief logic.

## Modes

- `direct_one_shot`: raw resume text only, one LLM call returns the full shared schema.
- `direct_fieldwise`: raw resume text only, focused field-group calls are merged by one final LLM call.
- `guided_reconciliation`: raw resume text plus current deterministic parser output, where deterministic output is only a non-authoritative hint.

## Run With A Fixture

```powershell
.venv\Scripts\python.exe experiments\resume_extraction_compare.py `
  --case-id ai_agent_backend `
  --runs 3 `
  --env-file .env.deepseek.local
```

## Run With A Private Local Resume

```powershell
.venv\Scripts\python.exe experiments\resume_extraction_compare.py `
  --input-file path\to\private_resume.txt `
  --runs 3 `
  --env-file .env.deepseek.local
```

Do not commit private input resumes or experiment outputs. Reports are written to `experiments/output/`, which is gitignored.

## Multidomain Flow Check

Run the resume-to-search-preview sanity check across synthetic non-engineering resumes:

```powershell
.venv\Scripts\python.exe experiments\multidomain_flow_check.py
```

This script does not call DeepSeek or live job providers. It runs local API use cases over the samples in `tests/fixtures/resumes/multidomain_samples/` and writes a Markdown report with parsed resume signals, confirmed profile fields, generalized search intent, provider queries, and pass/fail checks.

## Provider Recall Calibration

Run a small live provider recall check across the same multidomain samples:

```powershell
.venv\Scripts\python.exe experiments\provider_recall_calibration.py `
  --env-file .env.deepseek.local `
  --queries-per-case 2 `
  --limit-per-query 10
```

The default provider is `multi_source` with the current frontend sources:
`cuhksz_career`, `linkedin`, and `remoteok`. The script calls live selected
providers, so it can consume Serper requests when LinkedIn or `serper_web` is
included. It does not call DeepSeek, does not perform final LLM ranking, and
does not build Job Brief. Reports are written to `experiments/output/` as JSON
and Markdown.

Useful variants:

```powershell
.venv\Scripts\python.exe experiments\provider_recall_calibration.py `
  --provider multi_source `
  --source cuhksz_career `
  --source remoteok

.venv\Scripts\python.exe experiments\provider_recall_calibration.py `
  --provider serper_web `
  --env-file .env.deepseek.local
```

Required:

- `SERPER_API_KEY` or `JOBAGENT_SERPER_API_KEY` only for Serper-backed sources:
  `linkedin` and `serper_web`

Optional:

- `JOBAGENT_WEB_SEARCH_SITES=career.cuhk.edu.cn,zhipin.com,linkedin.com`

The report includes per-source raw counts, deduped counts, unretained counts,
missing URL/detail counts, detail coverage, provider warnings, provider query
results, and top candidates with source links.

## Metrics

Each report includes schema-valid rate, evidence-valid rate, unsupported field count, expected signal coverage, and output stability. The evaluator now also records wall-clock elapsed seconds for every run and the logical LLM request count for each mode, then reports per-mode averages in both JSON and Markdown summaries. This makes it easier to compare extraction quality against latency and request cost.

Evidence entries must use the standard shape:

```json
{ "value": "...", "quote": "..." }
```

Malformed evidence is normalized safely in the saved output, but still counted as invalid during evaluation.

## Environment

The experiment reads environment variables only from the file passed with `--env-file`, defaulting to `.env.deepseek.local`. Required:

- `DEEPSEEK_API_KEY`

Optional values follow the existing project conventions:

- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `JOBAGENT_LLM_TIMEOUT`
- `JOBAGENT_LLM_TEMPERATURE`

Secrets are not printed in reports or terminal output.
