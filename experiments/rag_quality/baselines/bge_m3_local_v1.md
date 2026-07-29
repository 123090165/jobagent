# bge-m3 Local Baseline v1

- Date: 2026-07-28
- Fixture: `career-private-v1`
- Embedding: Ollama `bge-m3`, 1024 dimensions
- Retrieval: authorized Chroma + BM25 with RRF
- Product path: bilingual query expansion, MCP scope token, current-resource reload

## Results

| Metric | Value |
|---|---:|
| Cases | 4 |
| Hit Rate | 1.000 |
| Mean Recall@K | 1.000 |
| Mean Precision@K | 0.333 |
| Mean Reciprocal Rank | 1.000 |
| Forbidden cross-user hits | 0 |
| Mean local latency | 2915 ms |

All expected resources ranked first. The deliberately high-overlap resource
owned by the second user was never returned.

Precision@K is low by construction because every current case has one labeled
relevant resource and requests three candidates. Add multi-relevant and hard
negative cases before using Precision@K as a release gate. Local latency includes
Ollama embedding plus MCP session setup and is a target for later optimization.
