# Search And Analysis Pipeline

## Provider Interface

All search sources produce normalized RawJobCandidate records. Current provider
names are:

- mock: deterministic local fixtures;
- cuhksz_career: public list and detail pages;
- remoteok: public JSON API;
- linkedin: discovery links through configured Serper search;
- serper_web: allowlisted web search snippets;
- multi_source: aggregation of selected backend sources;
- browser_helper: candidates supplied by the local browser extension.

The browser helper path may combine BOSS candidates with backend-native sources.
Provider selection and LLM selection are independent.

Provider adapters own network and source parsing. They must preserve source URL,
source label, raw evidence, warnings, and enough metadata for deduplication.

## Pipeline

~~~text
Search planning
-> Provider search
-> Candidate filtering
-> JD analysis
-> Profile matching
-> Result assembly
~~~

### Search Planning

Build typed logical queries and ranking signals from the confirmed profile and
user input, then translate them into source-specific tasks. Query selection
covers multiple intent types instead of truncating the first three strings.
LLM planning is optional. Plan assembly, quotas, normalization, query caps, and
safety rules remain deterministic.

### Provider Search

Execute a bounded query budget, normalize candidates, canonicalize source
identity, deduplicate, and enforce a candidate-pool cap. Different sources run
with bounded concurrency; tasks for the same source remain sequential. Merge
results in deterministic task order and preserve partial failures. Trace source
coverage, concurrency, missing details, duplicates, warnings, and query durations.

### Candidate Filtering

Apply structured hard constraints first. Explicit conflicts are rejected,
missing constraint evidence is marked unknown, and accepted/unknown candidates
continue to deterministic pre-ranking. In LLM mode, only the bounded pre-ranked
window is sent for scorecards. Validate indexes, scores, evidence, and result
shape. Fall back to deterministic ranking on request or quality failure.

### JD Analysis

Analyze selected candidates independently with bounded concurrency. Preserve
candidate order. One candidate may fall back without failing the full run.
Quality gates compare model output with deterministic evidence and reject
unsupported or materially incomplete analysis.

### Profile Matching And Assembly

Use analyzed JD evidence to compute the final score instead of reusing the
recall score. Reapply canonical identity so duplicate jobs cannot return after
ranking. Within a five-point score window, prefer new companies and sources to
avoid a homogeneous Top K without overriding a clear quality gap.

## LLM Boundary

Business logic calls the shared JSONChatLLM interface. DeepSeek is the current
default hosted provider. Mock and Ollama-compatible implementations may remain
for tests or local compatibility, but features must not import a DeepSeek
client directly.

analysis_mode controls whether a workflow is deterministic or LLM-assisted.
llm_provider controls which model service implements the LLM call.

Model output is never trusted only because it matches a schema. Validate:

- grounding in resume or JD evidence;
- required sections and useful coverage;
- bounded scores and valid candidate indexes;
- unsupported skill or responsibility injection;
- stale, sparse, or missing source data.

Fallback is a supported product result and must expose a concise reason.

## Observability

Persist one trace step per pipeline stage with:

- status and mode;
- duration;
- fallback reason;
- concise quality warnings;
- selected counts and bounded diagnostics.

Current detailed timing covers planning, provider query batches, candidate
filtering phases, and per-candidate JD analysis totals. Frontend client stages
cover helper checks, BOSS login/search, capture, and backend import.

Do not put full prompts, tokens, cookies, resumes, or large candidate payloads
in logs or trace details.

Future operational metrics should include:

- run success/failure and stale-running counts;
- provider availability and detail coverage;
- fallback reason distribution;
- LLM timeout/rate-limit counts;
- Top 5 relevance; user outcome metrics only after real behavior data exists.

## Search Quality Evaluation

Use fixtures and representative profiles to evaluate:

- useful unique candidates;
- duplicate and stale rates;
- missing URL and missing detail rates;
- Top 5 and Top 10 relevance;
- scorecard evidence quality;
- source diversity;
- analysis fallback frequency.

Network and hosted LLM calls stay out of the default test suite. Live provider
smoke and recall experiments are explicit commands under experiments/.

## Future Workflow Engine

Do not introduce LangGraph for the current fixed sequence. Reconsider it when
the workflow requires loops, policy branches, human pauses, and durable
checkpoint/resume. If introduced, wrap it behind a JobAgent orchestration
adapter and preserve current API, provider, LLM, and repository interfaces.
