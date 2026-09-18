# Workflows and Guardrails

## Local setup

The supported setup is Windows, Python 3.12, and Google Chrome:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\recreate_venv.ps1
.\venv\Scripts\python.exe --version
```

`recreate_venv.ps1` only removes the selected repository-local environment,
recreates it with `py -3.12`, upgrades pip, and installs `requirements.txt`.
Credentials are loaded at runtime by `src/user_secrets.py` into `SYN_USER` and
`SYN_PASS`.

## Supported data workflow

Run from the repository root. Omit `--headless` during initial live validation.

```powershell
# 1. Complete owner export
.\venv\Scripts\python.exe .\export_owners.py `
  --output output\owners-list.json

# 2. Read-only Top-100 scan and owner annotation
.\venv\Scripts\python.exe .\mark_top_100_owners.py `
  --input output\owners-list.json

# 3. Enrich the priority batch
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.top-100.json `
  --top-100-only

# 4. Compile completed research
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.top-100.enriched.json `
  --dossier-dir output\owner-research\top-100 `
  --selection top-100 `
  --output output\completed-enriched-owners-list.top-100.json `
  --mark-ai-enriched

# 5. After completed-research compilation, preview changes
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\completed-enriched-owners-list.top-100.json `
  --top-100-only `
  --ai-enriched-only `
  --not-updated-only

# 6. Apply only after reviewing the dry-run audit and testing a dummy
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\completed-enriched-owners-list.top-100.json `
  --top-100-only `
  --ai-enriched-only `
  --not-updated-only `
  --apply
```

The AI compiler may edit only `details[*].value` and the social array in a
separate derived file; it never changes `_baseline`. Dossiers become accepted
when terminal research passes strict validation and sets
`review.status=complete`. `compile_owner_research.py --mark-ai-enriched` sets
the workflow flag for usable complete or legacy-approved dossiers and resets
`workflow.updated_in_system=false` when a desired change is introduced. Only
values with confidence 70 or higher are imported.

`output/owner-research/all-by-loa/cohort.json` is the tracked corpus status
ledger. Its identity, order, vessel and LOA fields are immutable. Use
`sync_owner_cohort_status.py` to derive `workflow.researched` from terminal
production dossiers and to import only already-verified
`workflow.updated_in_system=true` states. The synchronizer is dry-run-first,
preserves imported true update flags, and requires an explicit
`--mark-not-updated` to clear one. Its optional `--audit` output is for a
deliberately retained migration or update record, not ordinary progress. The
cohort requires researched owners to form a contiguous prefix, and its root
`workflow_summary` is the sole progress authority, including the completed
prefix and next unresearched owner. Do not retain ignored progress markers,
tranche summaries, or numbered cumulative compilations as parallel state.
Schema-v8 tags follow the canonical
[owner-tag governance policy](OWNER_TAG_GOVERNANCE.md). Production resolution
exposes active assignments and canonical merge redirects only. Candidate,
inactive, unknown, ambiguous, mismatched, or duplicated references cannot
compile as active assignments; legacy references remain reportable for the
later in-place consolidation. Owner research cannot create formal candidates.
Compilation never maps or writes website tag IDs.

`update_owner_tags.py` is the separate live reconciliation path for completed
schema-v8 dossiers. It compares canonical names because catalogue IDs are local
research identifiers and website row IDs identify owner-tag associations. Keep
pure tag planning in `src/diffing.py`, HTML parsing in `src/parsers.py`, Selenium
mechanics in `src/browser_update.py`, and login/auditing in the entrypoint.

For an LOA-prioritised research batch, use a vessel-enriched input with
`--selection largest-loa`. This selector must include only fully ranked owners,
order them by metric largest-current-vessel LOA, and apply `--limit` as an
exact count. It must not silently include incomplete vessel scans. Use
`--selection all-by-loa` for resumable cumulative research over the complete
owner file; ranked owners remain first by LOA and owners without a ranked
current vessel follow rather than being discarded.

Resume checkpointed read stages with their explicit flag:

```powershell
.\venv\Scripts\python.exe .\mark_top_100_owners.py `
  --input output\owners-list.json `
  --resume

.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.top-100.json `
  --output output\owners-list.top-100.enriched.json `
  --top-100-only `
  --resume
```

`--refresh` deliberately re-reads records; it does not itself mark an owner as
AI enriched or updated in the system.

## Change routes

### Login or session behavior

Change `src/auth.py`; keep selectors aligned with the established login form.
Do not persist cookies. `fetch_html` must continue to detect a returned login
page and fail clearly on session expiry.

### Report or edit-page HTML changes

- Owner list/details/social and owner-vessel parsing: `src/parsers.py`.
- Owner-vessel fetching, specification caching, and ranking:
  `src/owner_vessels.py`.
- Top-100 list and UBO parsing: `src/top_100.py`.
- URLs and timeouts: `src/constants.py`.

Update the smallest relevant parser and its fixture assertions. Do not weaken
missing-table/form errors into silent empty exports.

### JSON schema or persistence

Change constructors/validation in `src/io_utils.py` and workflow backfill in
`src/workflow.py`. Preserve schema-v1 compatibility for additive optional
fields; bump the schema only for incompatible changes. All long-running
exports must retain atomic, frequent checkpoints.

### Diff or update policy

Change pure planning behavior in `src/diffing.py` first and cover it in
`tests/test_diffing.py`. Keep Selenium mechanics in `src/browser_update.py`
and orchestration/auditing in `update_owners.py`.

Controlling fields (`unknown_name`, `mortality_status`) must be set before
dependent details fields. Rich text must use CKEditor when present and
synchronize the backing textarea before save.

### Workflow flags or batching

Centralize transitions and matching in `src/workflow.py`. Keep CLI filters in
the entrypoint scripts thin. A successful read/enrichment must not imply that
AI review or a live system update occurred.

## Safety guardrails

- Never print usernames, passwords, cookies, or page content containing
  credentials.
- Do not overwrite source owner JSON. Write derived, timestamped, or explicitly
  separate output files.
- Owner-vessel enrichment is read-only. Preserve raw measurements, cache each
  distinct vessel specification, and do not mark a ranking complete when any
  current-vessel LOA is unavailable.
- `reorder_vessel_owners.py` is dry-run by default. It may apply only the
  website's stable oldest-first start-date ordering, must checkpoint an audit
  after every vessel, and must verify the persisted relationship-ID order from
  a fresh edit-page read before reporting success.
- `mark_top_100_owners.py` is read-only: it may click the vessel edit link to
  reveal UBO data, but it must never locate or activate a save/submit control.
- `compile_owner_research.py` must never overwrite its owner input and must not
  mark pending, rejected, or unusable dossiers AI-enriched.
- `update_owners.py` remains dry-run unless `--apply` is present.
- `update_owners.py` must load the biography ignore list before authentication
  and must never plan or verify writes to `biography` or `long_biography` for
  a listed person ID. Missing or invalid protection config is a fatal error.
- `update_owner_tags.py` remains dry-run unless `--apply` is present. Applying
  additions must not imply authority to delete; removals additionally require
  `--replace-tags`.
- `update_owner_tags.py --offline` must not authenticate or read live owner
  pages. It may report lifecycle and record-frequency diagnostics, but cannot
  claim live additions or removals.
- The default two-dossier-record threshold suppresses low-frequency new live
  additions only. It is neither taxonomy approval nor evidence of unique
  people. Do not remove an already-live match solely because it is below the
  threshold.
- Destructive tag removal requires a successful live read, `--replace-tags`,
  and an explicitly reviewed dry-run manifest matching the requested removal
  set. Unresolved and lifecycle-incomplete legacy records cannot authorise
  removals.
- Keep clearing blanks behind `--allow-clear`.
- Keep removal of absent socials behind `--replace-socials`.
- Re-read live state before every planned save. A live-versus-baseline
  difference is a conflict, not authorization to overwrite.
- Re-export after saving and require a clean verification plan before setting
  `workflow.updated_in_system=true`.
- Do not infer a cohort update flag from compilation, tag-only work, or an
  unverified apply. Import it only from a verified refreshed owner document or
  set it explicitly after equivalent verification.
- Tag Add and Delete controls write immediately rather than at the overlay's
  Done action. Re-read the overlay before the first mutation, add canonical
  replacements before deleting old names, checkpoint every successful CRUD
  action, and re-fetch the owner page for verification. Tag-only updates must
  not set `workflow.updated_in_system`.
- Keep inputs and partial successes recoverable through atomic checkpoints.
- Run the live reversible test only against a supplied, dedicated dummy person.
  If restoration is unconfirmed, preserve artifacts and report manual recovery
  instructions.
- Treat `examples/`, `output/`, screenshots, audits, and dummy artifacts as
  potentially sensitive and keep them out of Git.

## Quality gates

Run the offline suite:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

The parser tests require the local ignored fixtures under `examples/`. If they
are missing, report that environmental gap; do not fabricate replacement data
from memory.

Check syntax and accidental whitespace errors:

```powershell
.\venv\Scripts\python.exe -m compileall -q src export_owners.py mark_top_100_owners.py enrich_owner_vessels.py enrich_owners.py compile_owner_research.py reorder_vessel_owners.py update_owners.py update_owner_tags.py test_dummy_account.py
git diff --check
```

For parser or selector changes:

1. Run the targeted fixture test.
2. Run the full offline suite.
3. Smoke-test the affected read path with a record/page limit.
4. Use the reversible dummy test before any real update apply:

```powershell
.\venv\Scripts\python.exe .\test_dummy_account.py `
  --person-id DUMMY_ID `
  --apply
```

Never run the dummy test without explicit authority to change that supplied
dummy account.

## Release and handoff

There is no package build or deployment step. A change is ready to hand off
when:

- tests and compile checks pass;
- live selectors were smoke-tested when they changed;
- dry-run/apply safety defaults remain intact;
- generated or sensitive artifacts are absent from `git status`;
- README commands still match the CLIs;
- onboarding docs still match the implemented architecture.
