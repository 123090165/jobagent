# Project Challenge Decomposition

## Problem

Full-report LLM generation caused `ValidationError` and `LLMServiceError` with small local models. The old ProjectChallengeAgent asked the model to emit a complete `ProjectChallengeReport`, which has many fields, nested lists, and schema-sensitive values.

## Design

ProjectChallengeAgent now acts as a project interview challenge orchestrator:

```text
requirement selection
-> evidence binding
-> one-question generation
-> validation
-> per-question fallback
-> deterministic assembly
```

The LLM only generates one `GeneratedGroundedQuestionDraft` at a time. Code owns requirement selection, resume evidence binding, schema assembly, final `ProjectChallengeReport` validation shape, and fallback behavior.

## Why This Is More Reliable

The small-step prompt has small input, small output, and a small schema. A failure affects only one question instead of invalidating the whole report. The final report shape stays deterministic because Python assembles the existing `ProjectChallengeReport` fields.

## Local Model Implications

`qwen2.5:1.5b` may fail full schema generation under the local 8k context setup, but it can still be useful for one-question generation. The prompt sends only the requirement, match level, bound resume evidence, job title, and job category instead of the full resume, full JD, and full match report.

## Fallback Granularity

Old behavior:

```text
full ProjectChallengeReport generation fails
-> entire ProjectChallengeAgent fallback
```

New behavior:

```text
one question generation fails
-> fallback only for that question
-> assemble the final report with successful LLM questions plus deterministic fallback questions
```

If requirement planning produces no usable requirements, or every LLM item fails, the agent still returns the original deterministic report fallback.

## Safety

The evidence binder only uses evidence already present in `MatchReport` or `ResumeProfile`. It does not invent projects, companies, metrics, tools, achievements, or unsupported resume evidence. Missing requirements are framed as honest preparation gaps.
