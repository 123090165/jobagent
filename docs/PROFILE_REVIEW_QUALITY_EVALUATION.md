# Profile Review Quality Evaluation

## Goal

Verify whether the current profile pipeline can parse resumes, produce editable
profile drafts, use LLM enrichment safely, and generate confirmed profiles ready
for persistence.

## Cases

- AI Agent / Backend
- Embedded STM32
- ML Audio / ASR
- Finance / FA Analysis
- Mixed Language
- Weak Resume

## Evaluation Modes

- `deterministic_only`
- `llm_enriched`

## Artifacts

`docs/demo_outputs/profile_review_quality_eval/`

## Human Review Instructions

Review deterministic output first. Then review LLM-enriched output. Then inspect
`comparison_summary.md`. Judge whether profile extraction is good enough to
support job search and matching.
