# Ollama LLM Workflow Evaluation

## Purpose

This experiment compares the deterministic JobAgent workflow with selected local Ollama-backed LLM modes. ProjectChallengeAgent now uses small-step question generation so item-level fallback can be inspected separately from full-agent fallback.

## Run Commands

Local Ollama example:

```bash
set JOBAGENT_LLM_BASE_URL=http://127.0.0.1:11434/v1
set JOBAGENT_LLM_API_KEY=ollama
set JOBAGENT_LLM_MODEL=qwen2.5:1.5b
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
- mode=llm means that agent returned schema-valid LLM result(s). ProjectChallengeAgent may still have item-level fallbacks.
- mode=fallback means the LLM path was requested but failed and the agent used the deterministic fallback.
- fallback_reason usually identifies validation, request, parsing, or service failures.
- Token estimates use `max(1, round(len(text) / 4))` and are conservative approximations, not billing records.
- Actual usage fields are included only when the OpenAI-compatible response contains usage metadata.

## Experiment Limits

- ProjectChallengeAgent uses one-question prompts instead of one full-report prompt.
- Small local models may fail individual JSON objects even when the workflow remains stable through per-question fallback.
- Token estimates approximate the prompt reconstruction inside each agent; they are useful for comparison, not exact accounting.
- Running only `--mode mock` validates the harness but does not evaluate Ollama model quality.

## Latest Local Run

- generated_modes: ollama-project-challenge-only
- generated_at: 2026-06-11T02:15:04+00:00

## ProjectChallenge Decomposition Update

- planner_added: deterministic selection prioritizes partial matches, then core matched requirements, then important missing requirements.
- evidence_binder_added: question prompts only receive bound evidence from `MatchReport` or `ResumeProfile`.
- small_step_prompt_added: `project_question_generator_v1` asks for one JSON question draft at a time.
- per_question_fallback_added: individual LLM failures fall back locally; whole-agent fallback is reserved for no selected requirements or all-item failure.
- evaluation_fields_added: step reports include `llm_success_count`, `fallback_count`, `item_fallback_reasons`, and `prompt_version`.

## Local Ollama 8k 1.5B Decomposition Run

- actual_model: qwen2.5:1.5b
- mode_run: ollama-project-challenge-only
- project_challenge_step_mode: llm
- project_challenge_llm_success_count: 6
- project_challenge_item_fallback_count: 0
- grounded_questions: 6
- basic_questions: 1
- main_observation: ProjectChallengeAgent no longer failed as a whole in the isolated local Ollama run; qwen2.5:1.5b generated schema-valid one-question drafts for all selected requirements.
