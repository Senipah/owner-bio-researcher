# Agent Onboarding

## Purpose

This repository automates a safety-first workflow for exporting Superyacht
Network owners, prioritising current owners of YB Top 100 vessels, enriching
owner records, and applying reviewed JSON changes through the website.

## Read order

1. Read [README.md](README.md) for the supported human workflow and CLI usage.
2. Read [docs/ai/PROJECT_CONTEXT.md](docs/ai/PROJECT_CONTEXT.md) for the
   architecture, schemas, and state model.
3. Read
   [docs/ai/WORKFLOWS_AND_GUARDRAILS.md](docs/ai/WORKFLOWS_AND_GUARDRAILS.md)
   before changing browser automation, persistence, or update behavior.
4. Inspect the relevant entrypoint and its modules under `src/`.

## Working set

- `export_owners.py`: paginated owner-list export.
- `mark_top_100_owners.py`, `src/top_100.py`, `src/workflow.py`: Top-100
  vessel export, read-only UBO scan, annotations, and workflow flags.
- `enrich_owners.py`, `src/enrichment.py`, `src/parsers.py`: details and
  social enrichment.
- `compile_owner_research.py`, `src/research_batch.py`: validated AI dossier
  compilation and HTML review reporting.
- `update_owners.py`, `src/diffing.py`, `src/browser_update.py`: conflict-aware
  planning, browser writes, and post-save verification.
- `src/auth.py`, `src/io_utils.py`, `src/constants.py`: shared authentication,
  atomic JSON persistence, URLs, and schema version.
- `test_dummy_account.py`: reversible live write test for a dedicated dummy.
- `tests/`: offline parser, persistence, diff, and workflow tests.

## Core invariants

- Never log or persist credentials or authenticated cookies.
- Owner and Top-100 inputs are never overwritten.
- Top-100 scanning must never submit or save a form.
- Owner updates are dry-run by default and must re-read live values before
  saving.
- Blank clears and social removals require their separate explicit flags.
- Never overwrite a live value that differs from the immutable export
  baseline; report a conflict instead.
- Set `workflow.updated_in_system=true` only after a live save is re-exported
  and verified.
- Keep pending research `workflow.ai_enriched=false`; only an explicitly
  approved dossier may be compiled with that flag enabled.
- Do not commit generated output or the ignored `examples/` snapshots.

## Validation baseline

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m compileall -q src export_owners.py mark_top_100_owners.py enrich_owners.py compile_owner_research.py update_owners.py test_dummy_account.py
git diff --check
```

Parser tests require the local, ignored HTML fixtures under `examples/`.
