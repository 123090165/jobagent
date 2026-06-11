# Ollama LLM Workflow Evaluation

## Purpose

This experiment compares the deterministic JobAgent workflow with selected local Ollama-backed LLM modes. JDAnalysisAgent uses a prompt registry plus quality gate, and ProjectChallengeAgent uses small-step question generation so item-level fallback can be inspected separately from full-agent fallback.

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
- JDAnalysisAgent quality_warnings come from the JD quality gate after schema validation.
- ProjectInterviewAgent llm_success_count and fallback_count are per-question decomposition metrics.
- Token estimates use `max(1, round(len(text) / 4))` and are conservative approximations, not billing records.
- Actual usage fields are included only when the OpenAI-compatible response contains usage metadata.

## Experiment Limits

- JDAnalysisAgent schema-valid output can still fall back when the quality gate detects weak extraction.
- ProjectChallengeAgent uses one-question prompts instead of one full-report prompt.
- Python validates LLM output and assembles final artifacts instead of trusting large LLM reports directly.
- Small local models may fail individual JSON objects even when the workflow remains stable through per-question fallback.
- Token estimates approximate the prompt reconstruction inside each agent; they are useful for comparison, not exact accounting.
- Running only `--mode mock` validates the harness but does not evaluate Ollama model quality.

## Latest Local Run

- generated_modes: ollama-project-challenge-only
- generated_at: 2026-06-11T05:18:36+00:00

## Integrated LLM Control Surfaces

- JDAnalysisAgent uses the prompt registry plus a quality gate.
- ProjectChallengeAgent uses decomposition, one-question generation, and per-question fallback.
- LLM output is validated and assembled by Python before becoming workflow artifacts.

## Local Ollama 8k 1.5B Integration Run

- actual_model: qwen2.5:1.5b
- jd_only_step_mode: fallback
- jd_only_fallback_reason: ValidationError
- jd_only_quality_warnings: none because schema validation failed before the quality gate
- project_challenge_step_mode: llm
- project_challenge_llm_success_count: 6
- project_challenge_item_fallback_count: 0
- main_observation: JDAnalysisAgent fallback remained explicit and traceable, while ProjectInterviewAgent used the small-step path and reported per-question success/fallback metrics.
