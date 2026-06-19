# Git Workflow

Use small branches and small commits.

## Branches

- Keep `main` stable.
- Use `codex/<short-purpose>` for Codex cleanup and feature work.
- Keep each branch focused on one product or cleanup goal.

## Commit Shape

Prefer concise commit messages:

```text
feat: add job brief usecase
fix: handle empty resume upload
docs: canonicalize docs index
test: cover job search trace steps
chore: remove legacy docs
```

## Pre-Commit Checks

Run the checks that match the change:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m compileall app
cd web
npm run build
```

Do not commit ignored local artifacts:

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `web/dist/`
- `web/node_modules/`
- `.env`
- `.env.*`

## Cleanup Policy

When deleting legacy code or docs:

- verify imports first
- delete in staged batches
- run tests after each risky batch
- update `docs/CLEANUP_AUDIT.md` and `docs/LEGACY_MAP.md`
- do not create `_archive/`
