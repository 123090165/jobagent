# Ollama LLM Workflow Evaluation

## Purpose

This experiment compares the deterministic JobAgent workflow with selected local Ollama-backed LLM modes. It is an evaluation harness only; it does not change agent prompts, schemas, storage, workflow core, or product behavior.

## Run Commands

Local Ollama example:

```bash
set JOBAGENT_LLM_BASE_URL=http://127.0.0.1:11434/v1
set JOBAGENT_LLM_API_KEY=ollama
set JOBAGENT_LLM_MODEL=qwen2.5:0.5b
set JOBAGENT_LLM_TEMPERATURE=0
set JOBAGENT_LLM_TIMEOUT=120

.venv\Scripts\python.exe scripts\run_ollama_workflow_evaluation.py --mode all
```

Offline mock-only run:

```bash
.venv\Scripts\python.exe scripts\run_ollama_workflow_evaluation.py --mode mock
```

## Environment Variables

- JOBAGENT_LLM_BASE_URL: OpenAI-compatible endpoint, for example `http://127.0.0.1:11434/v1`.
- JOBAGENT_LLM_API_KEY: Any non-empty key accepted by the local server, for example `ollama`.
- JOBAGENT_LLM_MODEL: Model name served by Ollama; the script does not hard-code this.
- JOBAGENT_LLM_TEMPERATURE: Optional, defaults through LLMConfig when omitted.
- JOBAGENT_LLM_TIMEOUT: Optional timeout in seconds.

If an LLM mode is requested without the required variables, the script prints:

```text
LLM is not configured. Set JOBAGENT_LLM_BASE_URL, JOBAGENT_LLM_API_KEY, JOBAGENT_LLM_MODEL.
```

## Output Files

- Output directory: `docs/demo_outputs/ollama_workflow_eval`
- Per-mode reports: `mock_report.md`, `ollama_jd_only_report.md`, `ollama_resume_optimize_only_report.md`, `ollama_project_challenge_only_report.md`, `ollama_all_llm_report.md` when those modes are run.
- Comparison summary: `comparison_summary.md`.
- This summary: `docs/OLLAMA_LLM_WORKFLOW_EVALUATION.md`.

## How To Read The Results

- mode=mock means the deterministic fallback path ran intentionally.
- mode=llm means that agent returned a schema-valid LLM result.
- mode=fallback means the LLM path was requested but failed and the agent used the deterministic fallback.
- fallback_reason usually identifies validation, request, parsing, or service failures.
- Token estimates use `max(1, round(len(text) / 4))` and are conservative approximations, not billing records.
- Actual usage fields are included only when the OpenAI-compatible response contains usage metadata.

## Experiment Limits

- Prompt text is not changed in this experiment.
- Small local models may fail JSON schema requirements even when the workflow remains stable through fallback.
- Token estimates approximate the prompt reconstruction inside each agent; they are useful for comparison, not exact accounting.
- Running only `--mode mock` validates the harness but does not evaluate Ollama model quality.

## Latest Local Run

- generated_modes: mock
- generated_at: 2026-06-10T14:17:27+00:00
