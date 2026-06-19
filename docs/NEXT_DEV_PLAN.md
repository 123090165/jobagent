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

## v4.6.2 Parser Regression Corpus (current)

- turn existing realistic resume cases into stricter parser regression fixtures
- assert key positive behavior: real project, work, education, skill, and highlight extraction
- assert key negative behavior: no fabricated projects, no fabricated work items, no separator pollution
- keep tests deterministic and free of real LLM/network dependencies
- intentionally establish a stable regression baseline before deeper deterministic parser changes

## v4.6.3 Deterministic Parser Hardening (next)

- improve section heading coverage for English, Chinese, and mixed resumes
- improve multi-line project grouping
- improve education/work/project boundary detection
- improve missing-info and quality-warning precision
- avoid a large parser architecture split until behavior is pinned by tests

## v4.6.4 Evidence-based LLM Resume Extraction

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
