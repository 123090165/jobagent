# LLM-assisted Profile Enrichment

## Problem

Section-based parser improves deterministic extraction, but some structured
meaning still needs semantic interpretation.

## Design

```text
resume_text
-> section-based parser
-> baseline ResumeProfileReviewResult
-> per-item LLM enrichment
-> schema validation
-> evidence grounding check
-> suggestions
-> user confirmation
```

## Why LLM does not replace parser

The parser provides the stable factual baseline. LLM enrichment only produces
evidence-bound suggestions that sit beside the baseline. It does not overwrite
`parsed_profile`.

## Guardrails

- source_quote required
- no unsupported metrics
- no unsupported skills
- no unsupported entities
- per-item fallback
- baseline always returned

## API

`POST /resume/profile-enrichment`

Request:

```json
{
  "resume_text": "...",
  "target_roles": ["Backend Engineer"],
  "use_llm": false
}
```

Response includes:

- `baseline_review`
- `enrichment_suggestions`
- `quality_warnings`
- `missing_info_questions`
- `llm_success_count`
- `fallback_count`
- `discarded_suggestion_count`

## Next Step

v3.5 adds a Slate-like Profile Review UI where users can inspect section cards,
accept/edit/reject evidence-bound suggestions, answer missing-info questions,
and confirm a profile draft without letting LLM output overwrite the
deterministic baseline automatically.
