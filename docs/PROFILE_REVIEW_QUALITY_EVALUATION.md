# Profile Review Quality Evaluation

## Goal

Verify that the profile-review pipeline can:

- parse realistic resume text deterministically
- build editable review drafts
- apply evidence-checked LLM enrichment safely
- produce confirmed profiles that are ready for persistence

## Coverage Focus

The v3.8 suite expands deterministic parser coverage for:

- AI health / biomedical signal resumes
- ML / audio / ASR resumes
- business / FA / research-style resumes
- noisy and unstructured resume text

## Evaluation Modes

- `--mode deterministic`
- `--mode llm`
- `--mode both`

## LLM Provider Options

The evaluation script supports:

- `--llm-provider mock`
- `--llm-provider ollama`
- `--llm-provider deepseek`

Use `--real-llm` only when you want the script to call a real provider.

### Ollama

Ollama is used through its OpenAI-compatible endpoint. Set local `.env` values such as:

```env
JOBAGENT_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
```

### DeepSeek

DeepSeek is used through its OpenAI-compatible chat completions API:

- base URL: `https://api.deepseek.com`
- endpoint: `/chat/completions`
- default model: `deepseek-v4-flash`
- optional model: `deepseek-v4-pro`

Set a local `.env` before running real DeepSeek evaluation:

```env
JOBAGENT_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

Do not commit a real `DEEPSEEK_API_KEY`.

If `DEEPSEEK_API_KEY` is empty, the real DeepSeek path is skipped by falling back cleanly instead of breaking the evaluation run.

## Example Commands

```bash
.venv\Scripts\python.exe scripts\run_profile_review_quality_evaluation.py --mode both --llm-provider mock --output-dir docs/demo_outputs/profile_review_quality_eval

.venv\Scripts\python.exe scripts\run_profile_review_quality_evaluation.py --mode both --real-llm --llm-provider ollama --output-dir docs/demo_outputs/profile_review_ollama_eval

.venv\Scripts\python.exe scripts\run_profile_review_quality_evaluation.py --mode both --real-llm --llm-provider deepseek --output-dir docs/demo_outputs/profile_review_deepseek_eval
```

## Artifacts

Main synthetic outputs live under:

- `docs/demo_outputs/profile_review_quality_eval/`
- `docs/demo_outputs/search_ready_profile_eval/`

Optional real-provider runs can be written to:

- `docs/demo_outputs/profile_review_ollama_eval/`
- `docs/demo_outputs/profile_review_deepseek_eval/`

The search-ready profile artifacts are deterministic only. They evaluate the
derived candidate profile layer after parsing/profile review and do not call an
external LLM.

## Review Order

1. Inspect deterministic output first.
2. Compare it with `llm_enriched` output.
3. Read `comparison_summary.md`.
4. Confirm that weak resumes are not over-scored and that save payloads remain valid.
