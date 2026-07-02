# Next Development Plan

Last updated: 2026-07-02

## Current Status

The current product flow is:

```text
Resume Intake
-> Resume Review
-> Profile Draft
-> Confirmed Profile
-> Search Preview
-> Job Search Run
-> Job Brief later
```

Job Brief remains postponed. The next priority is to make Job Search recall,
ranking, and explanation reliable enough that later Job Brief output can be
grounded in real provider candidates and real JD evidence.

## Completed Baseline

### v4.6 Resume Analysis Hardening

Completed work:

- `v4.6.1` Truthfulness Fix
- `v4.6.2` Parser Regression Corpus
- guided LLM resume review with deterministic fallback
- sanitized LLM fallback warnings
- frontend visibility for analysis mode/provider/fallback warnings
- regression protection against fabricated projects and work experience

Outcome:

```text
ResumeDocument -> trustworthy ParsedResumeReview -> trustworthy ProfileDraft
```

Remaining limitation:

- deterministic resume extraction is safer, but not yet high-quality across all
  domains;
- future parser/LLM extraction work should remain evidence-based and
  regression-tested.

### v4.7 Baseline Job Search Hardening

Completed work:

- Search Preview split from Job Search execution
- focused provider query generation from confirmed profile/search intent
- broader candidate preservation; candidates are not dropped only because
  company/location/detail fields are incomplete
- scorecard-style candidate filtering/ranking
- multi-source provider support:
  - `cuhksz_career`
  - `linkedin` via Serper-backed public job-link discovery
  - `remoteok` via public JSON API
  - `serper_web`
  - `multi_source`
- frontend checkboxes for selected recruiting websites
- provider status and selected-source visibility
- multidomain flow experiment scaffolding
- web search recall experiment scaffolding
- old unused service cleanup documented in
  `docs/DELETED_FILES_2026_06_25.md`

Current stable commit:

```text
92a0fbf feat: harden job search recall flow
```

## Current Stage: v4.7 Job Search Reliability

Goal:

```text
ConfirmedProfile
-> SearchIntent
-> provider-specific broad recall
-> preserved candidate pool
-> evidence-based ranking
-> explainable top results
```

Primary engineering objective:

- improve recall without turning provider queries into long, over-constrained
  keyword strings;
- keep platform retrieval broad and cheap;
- move precision into ranking and evidence checks;
- keep every final result traceable to provider URL/snippet/detail evidence.

## v4.7.1 Multidomain Flow Evaluation

Purpose:

- verify that the chain works beyond the original health-algorithm test resume;
- use realistic resumes from different domains;
- inspect each intermediate artifact:
  - resume review
  - profile draft
  - confirmed profile
  - search intent
  - provider queries
  - provider candidates
  - ranking output

Expected output:

- one Markdown report under `experiments/output/`
- pass/fail notes for each domain
- concrete bugs or weak assumptions converted into targeted tasks

Do not:

- tune only for one resume/domain;
- add a large new framework;
- require real LLM/network calls in pytest.

Latest local check:

```text
experiments/output/20260702T124629Z_multidomain_flow_check.md
Cases: 3/3 passed
```

Findings:

- the chain no longer drifts back to the original health-algorithm/backend test
  domain for brand marketing, museum/cultural research, or supply-chain resumes;
- the experiment now uses an injected fake JSON LLM and does not call local
  Ollama, DeepSeek, or live providers;
- non-technical resume `target_signals` now use domain-specific labels such as
  marketing, museum/cultural research, and supply-chain/logistics;
- deterministic skill extraction can still admit noisy tokens such as `Git`,
  `ACC`, and `FA` in humanities-style samples;
- generalized intent still exposes broad role families such as `data` or
  `operations`, but provider queries no longer use those low-value terms as
  standalone searches when explicit roles are available.

Follow-up tasks:

- reduce short/acronym skill noise in deterministic extraction;
- continue calibrating when broad role families should remain visible as intent
  labels versus executable provider queries.

## v4.7.2 Ranking Rubric Hardening

Purpose:

- make LLM-assisted ranking more stable and auditable;
- keep deterministic fallback available;
- ensure top results are ranked by JD evidence, not just query overlap.

Required scoring dimensions:

- role alignment
- domain/industry alignment
- skill evidence
- experience/project evidence
- location/work arrangement fit
- seniority fit
- missing evidence / uncertainty
- risk flags

Implementation constraints:

- structured scorecard output;
- bounded scores;
- explicit evidence quotes/snippets when available;
- no invented companies, URLs, duties, or requirements;
- tests use fake LLM responses and fixtures.

Current implementation notes:

- the LLM ranking prompt defines role, domain, skill, seniority/work-type,
  location, JD evidence, and risk-penalty dimensions;
- deterministic fallback now emits the same scorecard shape, including bounded
  `score_breakdown`, match reasons, risks, and evidence snippets;
- generic tools are treated as weaker support than role/domain evidence;
- sparse JD details or missing source URLs reduce confidence but do not
  automatically discard candidates.

## v4.7.3 Provider Recall Calibration

Purpose:

- compare CUHKSZ direct search, LinkedIn discovery, RemoteOK API, and optional
  Serper broader web search;
- measure useful candidate count, duplicate rate, missing detail rate, and top10
  relevance;
- tune provider query limits and candidate pool caps.

Likely improvements:

- provider-specific query budgeting;
- source-level trace details in UI;
- clear warning when a selected source is configured but weak for the current
  profile domain;
- optional larger recall pool before ranking.

## v4.7.4 Frontend Search Result Usability

Purpose:

- make Search Preview and Search Result easier to audit manually;
- expose enough details to diagnose bad search output.

Likely UI additions:

- selected provider/source badges;
- provider query list grouped by source;
- candidate source URL and detail status;
- score breakdown;
- evidence/risk sections;
- "why this ranked here" explanation.

Do not:

- spend time on visual polish before recall/ranking quality is acceptable.

## Later: Job Follow-up And Job Brief

Only after Search top results are reliable:

- ask follow-up questions about a specific job;
- explain strengths and risks;
- suggest resume tailoring;
- generate application strategy;
- generate Job Brief.

Target later flow:

```text
JobSearchResult -> Job Detail Q&A -> Job Brief
```

Job Brief should not be built on weak search results.
