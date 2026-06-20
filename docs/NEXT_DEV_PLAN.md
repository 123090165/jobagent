# Next Development Plan

## v4.6 Resume Analysis Hardening

Goal:

```text
ResumeDocument -> trustworthy ParsedResumeReview -> trustworthy ProfileDraft
```

Job Brief is postponed until resume analysis is reliable. The immediate priority is to make parser and LLM behavior honest, observable, and regression-tested before downstream job search matching or brief generation depends on it.

## v4.6.1 Truthfulness Fix

- ensure `use_llm=true` is not blocked by cached deterministic parsed reviews
- show useful sanitized LLM fallback reasons
- stop deterministic parser fallback from inventing `General project`
- stop deterministic parser fallback from inventing work experience from whole-resume text
- make Resume Review UI show LLM toggle state, analysis mode, provider status, and fallback warnings

## v4.6.2 Parser Regression Corpus

- turn existing realistic resume cases into stricter parser regression fixtures
- assert key positive behavior: real project, work, education, skill, and highlight extraction
- assert key negative behavior: no fabricated projects, no fabricated work items, no separator pollution
- keep tests deterministic and free of real LLM/network dependencies
- intentionally establish a stable regression baseline before deeper deterministic parser changes

## v4.6.3 Guided LLM Resume Review Integration (current)

- use deterministic parsing as a non-authoritative candidate profile
- send raw resume text plus the deterministic candidate into guided LLM review
- treat raw resume text as the only source of truth
- persist successful guided review as `analysis_mode="llm_guided"`
- keep deterministic fallback with sanitized warnings when LLM is unavailable, fails, or returns invalid output
- keep tests deterministic with fake JSON LLMs and no real DeepSeek/network calls

## v4.6.4 CUHKSZ Live Job Search Verification (next)

- verify live CUHKSZ provider behavior end to end against the existing job search flow
- keep provider behavior scoped and observable
- do not resume Job Brief until resume analysis and live search basics are trustworthy

## v4.6.5 Evidence-based extraction contract hardening

- require structured LLM output with evidence quotes for core fields
- validate LLM output with Python schemas
- reject or downgrade unsupported claims rather than merging hallucinated data
- keep deterministic parser as a safe baseline and use LLM as evidence-checked enrichment

## Later: Job Brief

Resume-dependent Job Brief work should resume only after `ParsedResumeReview` and `ConfirmedProfile` are reliable enough to support downstream matching claims.

Planned later output:

```text
JobSearchResult -> JobBrief
```

- match summary
- why this job matches
- risks and gaps
- resume tailoring suggestions
- interview/project challenge questions
- application strategy
