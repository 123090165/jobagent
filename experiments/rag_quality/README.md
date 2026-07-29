# Private RAG Quality Evaluation

This package evaluates JobAgent's authorized Resume Profile and Saved Job
retrieval independently from Search V2.

The versioned fixture contains synthetic business resources, expected resource
keys, and an intentionally stronger same-query document owned by another user.
Evaluator-only labels never enter the indexed text or MCP query.

Run the deterministic fixture check:

```powershell
python -m scripts.evaluate_rag_quality --mode lexical
```

Run the real management/outbox/MCP path:

```powershell
python -m scripts.evaluate_rag_quality --mode live
```

Live mode requires `JOBAGENT_RAG_MANAGEMENT_URL`, `JOBAGENT_RAG_MCP_URL`, and
`JOBAGENT_RAG_SERVICE_TOKEN`. It creates temporary JobAgent users, indexes
synthetic resources, executes current-resource verification, and archives all
fixture resources before exiting.

The default acceptance gate requires Hit Rate 1.0, MRR at least 0.75, and zero
forbidden hits. Precision@K remains descriptive because each current case has
one labeled relevant resource and requests three candidates.
