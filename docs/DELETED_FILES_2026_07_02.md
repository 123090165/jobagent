# Deleted Files - 2026-07-02 Provider Recall Cleanup

Cleanup date: 2026-07-02  
Branch: `codex/v4-curated-job-crawler-provider`

This cleanup removed experiment-only code that was superseded by the broader
provider recall calibration flow.

## Deletion Rule Used

Files were deleted only when all of these were true:

- no production API, frontend page, repository, provider, or usecase imported the
  file;
- the replacement covers the same behavior plus the current multi-source search
  path;
- pytest has replacement coverage for the new experiment path.

## Deleted Files

| Deleted file | Type | Why it was removed | Current replacement / current path | Restore note |
| --- | --- | --- | --- | --- |
| `experiments/web_search_recall_check.py` | old experiment | Serper-only recall check no longer matched the current frontend path, which can combine CUHKSZ Career, LinkedIn discovery, and RemoteOK. | `experiments/provider_recall_calibration.py` supports `multi_source`, `cuhksz_career`, `linkedin`, `remoteok`, and `serper_web`, and reports per-source recall/detail stats. | Restore only if a dedicated Serper-only report is needed; otherwise use `--provider serper_web` on the new script. |
| `tests/test_web_search_recall_experiment.py` | old test | Tested only the deleted Serper-only experiment. | `tests/test_provider_recall_calibration_experiment.py` covers provider selection, fake-provider recall, Markdown output, and JSON serialization without network calls. | Restore with the old script only. |

## Code Cleanup

Removed unused private helpers from `app/services/job_search_planner.py` after
confirming via `git grep` that they were no longer referenced:

- `_build_deterministic_plan`
- `_normalize_plan`
- `_query_signal_seed`
- `_provider_query_signal_seed`
- `_looks_like_acronym`

The current query path is:

```text
ConfirmedProfile -> JobSearchIntent -> JobSearchPlan -> focused provider queries
```

## Verification

Run after this cleanup:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m compileall app experiments
cd web
npm run build
```
