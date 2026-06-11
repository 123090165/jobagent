# LLM Prompt and Quality Control

## Why Schema Validation Is Not Enough

LLM output can be valid JSON and still be unsafe to trust. The local qwen2.5:1.5b evaluation showed this clearly: `JDAnalysisAgent` returned schema-valid JSON, but extracted far fewer `required_skills` than the deterministic baseline and pushed the downstream match score from 77 to 27. JobAgent therefore treats schema validation as the first check, not the final quality decision.

## Prompt Registry

Prompt text now lives under `app/prompts/` and is loaded with `app.prompts.loader.load_prompt`.

Current JD prompt files:

- `app/prompts/jd_analysis/system.md`
- `app/prompts/shared/json_output_policy.md`
- `app/prompts/shared/evidence_policy.md`
- `app/prompts/shared/anti_hallucination_policy.md`

The JDAnalysis prompt version is `jd_analysis_v2`. The loader only accepts relative paths inside `app/prompts`, reads files as UTF-8, and raises clear errors for missing prompts or path traversal attempts.

## JDAnalysis Quality Gate

`app/services/jd_analysis_quality.py` evaluates schema-valid LLM `JobAnalysis` output before the workflow trusts it.

Rules currently checked:

- sparse `required_skills` for a longer JD
- LLM `required_skills` much fewer than the deterministic baseline
- responsibilities polluted by metadata such as role, company, or location lines
- verbose skill entries
- empty or verbose keywords
- simple grounding checks for job title, company, and location

## Fallback Policy

The JD analysis path is:

```text
LLM proposes JobAnalysis
-> Pydantic validates schema
-> JDAnalysis quality gate reviews extraction quality
-> fallback to deterministic baseline if risky
```

When the quality gate recommends fallback, the agent returns the deterministic baseline with:

```text
mode=fallback
fallback_reason=quality_gate_failed
quality_warnings=[...]
```

The workflow step trace keeps `quality_warnings` in runtime metadata, and the Ollama evaluation reports display those warnings.

## Local Model Evaluation Lesson

The qwen2.5:1.5b local Ollama run was not a simple success signal. It proved that a local model can return schema-valid JD output while still losing important requirements. This is why JobAgent keeps local LLM mode behind quality gates instead of enabling it by default.
