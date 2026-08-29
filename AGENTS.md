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
4. Read [docs/ai/OWNER_TAG_GOVERNANCE.md](docs/ai/OWNER_TAG_GOVERNANCE.md)
   before owner-tag research, catalogue, audit, or reconciliation work.
5. Inspect the relevant entrypoint and its modules under `src/`.

## Working set

- `export_owners.py`: paginated owner-list export.
- `mark_top_100_owners.py`, `src/top_100.py`, `src/workflow.py`: Top-100
  vessel export, read-only UBO scan, annotations, and workflow flags.
- `enrich_owner_vessels.py`, `src/owner_vessels.py`, `src/parsers.py`:
  read-only owner-to-vessel discovery, specification caching, LOA
  normalization, and descending owner ranking.
- `enrich_owners.py`, `src/enrichment.py`, `src/parsers.py`: details and
  social enrichment.
- `compile_owner_research.py`, `src/research_batch.py`: validated AI dossier
  compilation and HTML review reporting.
- `update_owners.py`, `src/diffing.py`, `src/browser_update.py`: conflict-aware
  planning, browser writes, and post-save verification.
- `update_owner_tags.py`, `src/owner_tags.py`, `src/parsers.py`,
  `src/diffing.py`, `src/browser_update.py`: dossier-driven tag reconciliation,
  guarded removals, immediate-write checkpoints, and post-write verification.
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
- Owner-tag updates are dry-run by default; additions require `--apply`, while
  removals additionally require `--replace-tags`.
- Blank clears and social removals require their separate explicit flags.
- Never overwrite a live value that differs from the immutable export
  baseline; report a conflict instead.
- Owner dossiers may assign only approved active tags. Unapproved concepts stay
  in the separate dossier candidate structure and never mutate the active
  catalogue from a single-owner research run.
- Set `workflow.updated_in_system=true` only after a live save is re-exported
  and verified.
- Set `review.status=complete` only after a terminal research decision passes
  strict validation. Compilation may set `workflow.ai_enriched=true` for
  complete or legacy-approved usable dossiers, and may import only values with
  confidence 70 or higher.
- Do not commit generated output or the ignored `examples/` snapshots.

## Validation baseline

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m compileall -q src export_owners.py mark_top_100_owners.py enrich_owner_vessels.py enrich_owners.py compile_owner_research.py update_owners.py update_owner_tags.py test_dummy_account.py
git diff --check
```

Parser tests require the local, ignored HTML fixtures under `examples/`.
