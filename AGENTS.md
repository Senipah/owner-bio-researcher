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
- `reorder_vessel_owners.py`, `src/vessel_owner_order.py`: dry-run-first
  vessel UBO relationship-order planning, explicit applies, audit
  checkpoints, and post-write verification.
- `enrich_owners.py`, `src/enrichment.py`, `src/parsers.py`: details and
  social enrichment.
- `compile_owner_research.py`, `src/research_batch.py`: validated AI dossier
  compilation and HTML review reporting.
- `sync_owner_cohort_status.py`, `src/cohort_status.py`: dry-run-first
  synchronization of tracked research and verified live-update status in the
  canonical all-by-LOA cohort.
- `.agents/skills/research-owner-biography/scripts/register_corpus_tag_candidates.py`,
  `activate_corpus_tag_manifest.py`, `backfill_corpus_tag_manifest.py`,
  `add_catalogue_tag.py`, `src/tags.py`: separate corpus-level taxonomy
  candidate registration, explicit global activation, exact reviewed-manifest
  dossier backfill, and lifecycle-aware tag resolution.
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
- Owner IDs in `config/biography-update-ignore-ids.json` must never have their
  short or long biography overwritten by `update_owners.py`.
- Owner-tag updates are dry-run by default; additions require `--apply`, while
  removals additionally require `--replace-tags`.
- Vessel-owner reordering is dry-run by default, must reproduce the site's
  stable oldest-first date ordering, and must re-read the relationship IDs
  after every applied PATCH before reporting success.
- Blank clears and social removals require their separate explicit flags.
- Never overwrite a live value that differs from the immutable export
  baseline; report a conflict instead.
- Owner dossiers may assign only approved active tags. Individual and batch
  owner research are closed-world: unrepresented facts remain in ordinary
  research structures and formal candidates may be created only by an explicit
  corpus-level taxonomy workflow or human global curation.
- Set `workflow.updated_in_system=true` only after a live save is re-exported
  and verified.
- The all-by-LOA cohort's identity and ranking fields are immutable. Its
  `workflow.researched` and `workflow.updated_in_system` flags may change only
  through the dry-run-first cohort-status synchronizer; verified-update imports
  are monotonic unless an owner is explicitly marked not updated. Its summary
  is the sole progress authority; do not maintain a parallel progress marker.
- Set `review.status=complete` only after a terminal research decision passes
  strict validation. Compilation may set `workflow.ai_enriched=true` for
  complete or legacy-approved usable dossiers, and may import only values with
  confidence 70 or higher.
- Do not commit generated output or the ignored `examples/` snapshots.

## Validation baseline

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m compileall -q src export_owners.py mark_top_100_owners.py enrich_owner_vessels.py enrich_owners.py compile_owner_research.py reorder_vessel_owners.py update_owners.py update_owner_tags.py test_dummy_account.py
git diff --check
```

Parser tests require the local, ignored HTML fixtures under `examples/`.
