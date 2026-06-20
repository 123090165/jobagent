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

## Environment

The experiment reads environment variables only from the file passed with `--env-file`, defaulting to `.env.deepseek.local`. Required:

- `DEEPSEEK_API_KEY`

Optional values follow the existing project conventions:

- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `JOBAGENT_LLM_TIMEOUT`
- `JOBAGENT_LLM_TEMPERATURE`

Secrets are not printed in reports or terminal output.

