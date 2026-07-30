# Offline Quality Evaluation

Only reusable, network-free evaluation assets are kept here.

## Search quality

`search_quality/` contains the deterministic replay corpus, metrics, reports,
and frozen baselines used to catch retrieval and ranking regressions.

## Private RAG quality

`rag_quality/` contains a privacy-aware retrieval corpus and evaluator. Run the
lexical baseline without external services:

```powershell
python -m scripts.evaluate_rag_quality --mode lexical
```

Use live mode only when the local JobAgent and Modular RAG services are
configured. Generated reports belong under ignored `output/` directories.
