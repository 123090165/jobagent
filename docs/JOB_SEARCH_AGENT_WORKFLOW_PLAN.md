# Job Search Agent Workflow Plan

## Current Decision

JobAgent does not use LangChain or LangGraph today. The current search pipeline is a
fixed workflow:

1. Search planning
2. Provider search
3. Candidate filtering
4. JD analysis
5. Profile matching
6. Result assembly

The near-term priority is to make this fixed workflow reliable, fast, observable,
and model-provider agnostic. DeepSeek can be the default runtime provider, but
business logic should continue to call the internal LLM provider interface instead
of importing or invoking DeepSeek directly.

Search configuration should keep two decisions separate:

- `analysis_mode` controls whether the workflow uses deterministic analysis or
  LLM-assisted planning/filtering/JD analysis.
- `llm_provider` controls which provider backs LLM-assisted analysis. DeepSeek is
  the default runtime provider, while Ollama and mock remain behind the same
  provider abstraction.

## Near-Term Work

### Parallel JD Analysis

JD analysis is independent per selected candidate after candidate filtering is
complete. The current implementation can run these calls with bounded parallelism:

- Keep the existing provider-agnostic LLM service interface.
- Use a small concurrency cap, initially `3`.
- Make the cap configurable with `JOBAGENT_JD_ANALYSIS_CONCURRENCY`.
- Preserve result order by candidate index.
- Let a single candidate fallback without failing the whole search run.
- Record concurrency and fallback counts in the JD analysis trace step.

Expected result: searches with multiple selected candidates should spend much less
wall-clock time in the JD analysis step, while staying within provider rate limits.

## Future LangGraph Candidate

LangGraph should be considered later if the workflow becomes a dynamic, stateful
agent graph instead of a fixed pipeline.

Potential nodes:

- Search planning node
- BOSS search node
- CUHKSZ search node
- LinkedIn search node
- RemoteOK search node
- Search recall evaluation node
- Query rewrite node
- JD detail completion node
- User confirmation node
- Resume tailoring node
- Application plan node
- Interview question generation node

Potential graph behavior:

- If recall is too low, rewrite queries and return to provider search.
- If BOSS fails or requires verification, branch to other providers.
- If a candidate has weak JD evidence, attempt detail completion before ranking.
- If an action needs user approval, pause at a confirmation node.
- If a node fails, retry or resume from the last checkpoint.
- If a later step needs more evidence, loop back to retrieval.

## Adoption Criteria

Do not introduce LangGraph only to model the current fixed workflow. Reconsider it
when at least two of these are true:

- Search includes conditional loops or automatic query expansion.
- Cross-provider fallback becomes policy-driven rather than UI-driven.
- Human-in-the-loop pauses are required inside a run.
- Node-level checkpoint, resume, and retry semantics become product requirements.
- Multiple downstream agent stages share the same run state.

If adopted, LangGraph should sit behind a JobAgent orchestration adapter. API
schemas, repositories, and business use cases should not depend directly on
LangGraph types.
