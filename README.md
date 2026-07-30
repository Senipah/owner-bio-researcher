# Owner Bio Researcher

This toolkit exports the complete Superyacht Network owner report, enriches
each owner with every editable details field and social-media link, and safely
applies reviewed JSON changes back through the website's edit overlays.

The normal workflow is:

1. Export the owner list.
2. Export the YB Top 100 vessels and mark their current owners.
3. Enrich current Top-100 owners with existing system details.
4. Produce evidence-backed AI research dossiers, a separate enriched owner
   file, and an HTML review report.
5. Run an update dry-run and inspect its audit report.
6. Test the update flow on a dedicated dummy person.
7. Apply the reviewed changes.

## Safety model

- Update runs are dry-runs unless `--apply` is present.
- Blank values are not written unless `--allow-clear` is present.
- Social links absent from JSON are not removed unless
  `--replace-socials` is present.
- Each enriched record contains an immutable `_baseline`. The updater compares
  it with both the edited value and the current live value. If live data changed
  since export, that field or social section is reported as a conflict instead
  of being overwritten.
- Inputs are never overwritten. Apply runs create a refreshed JSON file with a
  new baseline, plus a timestamped audit report.
- Credentials and browser cookies are not written to output files or logs.

## Requirements

- Windows
- Python 3.12 available through `py -3.12`
- Google Chrome
- A credentials file understood by `src\user_secrets.py`, providing
  `SYN_USER` and `SYN_PASS`

## Create or recreate the environment

From PowerShell in this repository:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\recreate_venv.ps1
```

The script only removes the repository-local `venv` directory, recreates it
with Python 3.12, upgrades pip, and installs `requirements.txt`.

Activation is optional. Every example below calls the venv interpreter
directly:

```powershell
.\venv\Scripts\python.exe --version
```

## 1. Export all owners

```powershell
.\venv\Scripts\python.exe .\export_owners.py
```

The default output is `output\owners-list.json`. The exporter follows the
report's Next link until it reaches the last page and checkpoints after every
page.

Useful options:

```powershell
.\venv\Scripts\python.exe .\export_owners.py `
  --output output\owners-list.json `
  --headless

.\venv\Scripts\python.exe .\export_owners.py `
  --output output\smoke-list.json `
  --max-pages 2
```

`--max-pages` is intended for smoke tests; omit it for the full export.

## 2. Mark current Top-100 owners

Run the Top-100 stage against the owner export before details enrichment:

```powershell
.\venv\Scripts\python.exe .\mark_top_100_owners.py `
  --input output\owners-list.json
```

This creates two files without overwriting the owner input:

- `output\owners-list.top-100.json`: the owner list with workflow flags and
  matched Top-100 relationships.
- `output\top-100-vessels.json`: the ranked vessel report, all report columns,
  ownership scan status, and current/historical UBO relationships.

The script exports every page with the `yb_100=t` filter, visits each
specification page, clicks **Edit Details & Specification**, reads the
**[NEW] Ultimate Beneficial Owners** section, and closes without submitting a
form. It checkpoints both outputs after every vessel.

Resume pending or failed vessels:

```powershell
.\venv\Scripts\python.exe .\mark_top_100_owners.py `
  --input output\owners-list.json `
  --resume
```

Re-export and scan the complete list again:

```powershell
.\venv\Scripts\python.exe .\mark_top_100_owners.py `
  --input output\owners-list.json `
  --refresh
```

For a read-only smoke test, export the full vessel list but inspect only one
vessel:

```powershell
.\venv\Scripts\python.exe .\mark_top_100_owners.py `
  --input output\owners-list.json `
  --limit-vessels 1 `
  --headless
```

Only relationships with a blank To date set
`workflow.is_top_100_owner=true`. Ended relationships remain under
`top_100.relationships` and set `top_100.historical_owner=true`.

Person IDs present in the UBO section but absent from the supplied full owner
export are recorded in the vessel file and cause a non-zero exit so they cannot
be missed.

## Optional: rank all owners by current-vessel LOA

Run the read-only vessel enrichment stage against the complete owner export:

```powershell
.\venv\Scripts\python.exe .\enrich_owner_vessels.py `
  --input output\owners-list.json `
  --headless
```

The default output is `output\owners-list.vessel-enriched.json`. The source
owner file is not overwritten. For each owner, the stage:

- reads the **Vessels Owned (UBO)** table on the owner profile;
- treats a blank **To** date as current ownership;
- fetches each distinct current vessel specification once;
- preserves raw LOA and gross-tonnage values;
- normalizes metre, foot, and foot/inch LOA values into `loa_m`;
- records the largest known current vessel and an explicit ranking status; and
- sorts the derived owner array by largest known current-vessel LOA.

Gross tonnage is retained when available but does not control the sort. An
owner is marked `incomplete` rather than fully ranked if any current vessel
has a failed or unparseable specification.

Resume partial owner and vessel checkpoints:

```powershell
.\venv\Scripts\python.exe .\enrich_owner_vessels.py `
  --input output\owners-list.json `
  --resume `
  --headless
```

Use `--workers` to adjust the bounded HTTP concurrency, or `--person-id` and
`--limit` for smoke tests. The default is four workers.

## 3. Enrich owner details and social profiles

```powershell
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.top-100.json `
  --top-100-only
```

The default output is `output\owners-list.top-100.enriched.json`. Every named
editable control in the details form is represented, including blank fields.
Selects retain both their visible value and internal option ID. Internal notes,
biography, and the longer biography are stored as HTML because the site uses
CKEditor.

An interrupted run can resume from its existing output:

```powershell
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.top-100.json `
  --output output\owners-list.top-100.enriched.json `
  --top-100-only `
  --resume
```

Targeted and diagnostic runs:

```powershell
# Re-fetch a specific person
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.top-100.enriched.json `
  --output output\one-owner.enriched.json `
  --person-id 8690 `
  --refresh

# Process at most ten eligible records
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.top-100.json `
  --top-100-only `
  --limit 10
```

Each owner records `pending`, `ok`, or `error`. Failures do not discard
successful checkpoints. A successful enrichment also sets
`workflow.owner_details_enriched=true`. Use `--exclude-top-100` in a later run
to process the remaining owners.

## Editing the JSON

Edit only:

- `owners[*].details[*].value`
- `owners[*].social_media_profiles`

Do not edit `person_id`, `profile_url`, `profile_key`, or `_baseline`.

For selects, change the human-readable `value`. The updater selects by visible
text and uses `option_id` only as a fallback. For a new social profile, provide
`type_id`, `type`, and `url`; `profile_key` may be omitted. Retain the existing
`profile_key` when changing an exported social URL so the updater can recognize
it as a replacement.

Blank fields remain in JSON intentionally. By default they are ignored by the
updater, allowing research to populate them without risking unrelated data.

Each owner also has four workflow booleans:

```json
{
  "is_top_100_owner": true,
  "owner_details_enriched": true,
  "ai_enriched": false,
  "updated_in_system": false
}
```

The Top-100 and details scripts maintain the first two. The research compiler
sets `ai_enriched=true` only for explicitly approved dossiers and resets
`updated_in_system=false` whenever it creates a new desired change. A verified
live apply sets `updated_in_system=true`.

## 4. Compile researched owners for review

Owner research is stored as one pending-review dossier per person under
`output\owner-research`. Compile those dossiers into a new owner document and
a standalone HTML report without changing the enriched input:

Each schema-v7 person dossier contains an unordered, source-hidden
`biography_brief` fact pool with multiple opening options, a 50-55 word short
`biography`, a fact-allocated, complementary two-paragraph `long_biography` of
90-190 words, the seven-dimension `editorial_assessment`, and independent
`wealth_creation_industry`, `primary_industry`, `wealth_origin`, and
`wealth_relationship` classifications. Both industry fields use the same
dictionary, including `Cryptocurrency`: the first records the sector that
created the original fortune, while the second records the current principal
private interests. Institution and unresolved-placeholder dossiers instead
contain an `editorial_note`; their biography values are null and never applied
to person fields.

The compiler retains the brief, biographies or editorial note, record type, and
all four classifications under each compiled owner's `ai_research` metadata
and shows the appropriate content in the review report. For people, it maps the
short biography to `details.biography` and maps the longer version to
`details.long_biography` whenever that form field is available. Equivalent
editable classification fields can be populated through reviewed dossier
proposals using their exact display labels. Compilation runs strict editorial
validation, including source-invisibility, date, figure, vessel-independence,
reader-orientation, career-scaffolding, transition, and conclusion checks.

Schema-v5 and earlier dossiers are intentionally stale under this contract.
Their source ledgers may be reused, but they must be migrated through the
schema-v7 unordered fact-pool and cross-owner editorial pass before
compilation. Schema-v6 dossiers already satisfy the current editorial
structure but require a separate classification migration that adds
`wealth_creation_industry` before schema-v7 compilation.

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.top-100.enriched.json `
  --dossier-dir output\owner-research\top-100-first-10 `
  --selection top-100 `
  --limit 10
```

The default outputs for this calibration run are:

- `output\research-enriched-owners-list.top-100.first-10.json`
- `output\research-enriched-owners-list.top-100.first-10.html`

`--selection top-100` is the default and orders unique current owners by their
minimum current Top-100 vessel rank. To compile a review sample of the 50
owners with the largest current yachts, start from a vessel-enriched owner
document and select the explicit LOA mode:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.vessel-enriched.json `
  --dossier-dir output\owner-research\largest-loa-first-50 `
  --selection largest-loa `
  --limit 50
```

This mode uses `vessel_ownership.loa_rank` and
`vessel_ownership.largest_current_loa_m`, takes exactly the first 50 owners,
and excludes owners whose vessel scan is missing or `incomplete`. Its default
outputs include `.largest-loa.first-50` in their filenames. Dossiers must
exist for every selected owner before compilation succeeds.

For a resumable Goal Mode research run over the complete owner file, paste the
prompt in
[`docs/goal-mode-all-owners-by-loa-research-prompt.md`](docs/goal-mode-all-owners-by-loa-research-prompt.md).
The prompt derives the next fixed 50-owner window from the last verified
cumulative checkpoint, resumes partial work within that window, and freezes
every earlier completed tranche. It also preserves the explicitly authorised
first-50 editorial exception without extending that exception to later owners.

The JSON retains each owner's immutable `_baseline`, contains only the selected
owners, and applies only dossier proposals with confidence 85 or higher.
Pending research remains `workflow.ai_enriched=false`, so it cannot be selected
by the normal `--ai-enriched-only` update command.

For an editorial repair or classification-calibration batch, add
`--compare-dossier-dir` to compare the earlier and current short biography,
long biography, wealth-creation industry, primary industry, wealth origin and
wealth relationship. The report renders side-by-side panels only for fields
whose material values changed, ignores biography HTML-wrapper and line-ending
differences, and summarises changed owners, field counts and wealth-origin
transitions. The comparison directory is read only and does not affect the
compiled owner JSON:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.vessel-enriched.enriched.json `
  --dossier-dir output\owner-research\all-by-loa-pair-repair `
  --compare-dossier-dir output\owner-research\all-by-loa `
  --selection all-by-loa `
  --limit 50
```

After human review, change each accepted dossier to `review.status=approved`
and record `reviewed_by` and `reviewed_at`. Recompile with
`--mark-ai-enriched` to make the reviewed file eligible for update dry-runs:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.top-100.enriched.json `
  --dossier-dir output\owner-research\top-100-first-10 `
  --selection top-100 `
  --limit 10 `
  --output output\approved-enriched-owners-list.top-100.first-10.json `
  --report output\approved-enriched-owners-list.top-100.first-10.html `
  --mark-ai-enriched
```

Rejected dossiers must also record `reviewed_by` and `reviewed_at`; their
proposals are left unapplied and their owners remain `ai_enriched=false`.

## 5. Preview and apply updates

Always start with a dry-run:

```powershell
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.top-100.enriched.json `
  --top-100-only `
  --ai-enriched-only `
  --not-updated-only
```

Audit reports are written beneath `output\audits`. Review planned changes,
skipped blanks, and conflicts before applying:

```powershell
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.top-100.enriched.json `
  --person-id 8690 `
  --apply
```

Potentially destructive options are separate and explicit:

```powershell
# Permit edited blank values to clear live fields
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.top-100.enriched.json `
  --person-id 8690 `
  --allow-clear `
  --apply

# Also remove live social profiles absent from the JSON array
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.top-100.enriched.json `
  --person-id 8690 `
  --replace-socials `
  --apply
```

After an apply run, continue future editing from the generated
`*.applied-<timestamp>.json` file because it contains the verified current
baseline.

## 6. Reversible dummy-account test

Use only a dedicated dummy person. The ID is supplied at runtime and is never
stored in source code:

```powershell
.\venv\Scripts\python.exe .\test_dummy_account.py `
  --person-id 12345 `
  --apply
```

The test:

1. Captures the complete initial details and social state.
2. Appends a unique internal-note marker and a temporary website link.
3. Saves through the real details and social iframe overlays.
4. Re-exports and verifies the changes.
5. Restores and verifies the exact initial state.

Before, changed, and restored JSON, screenshots, and `report.json` are written
under `output\dummy-tests`. A failed restoration exits non-zero and prints the
location of the before-state needed for manual recovery.

Run this test successfully before applying changes to multiple real owners.

## Offline tests

The offline suite uses the saved HTML fixtures and never logs in or writes to
the live site:

```powershell
.\venv\Scripts\python.exe -m pytest
```

## Troubleshooting

- If login fails, confirm that `src\user_secrets.py` loads `SYN_USER` and
  `SYN_PASS` in the current Windows account.
- If Chrome opens but Selenium cannot attach, close other automated Chrome
  sessions and retry.
- If enrichment returns the login page, the session expired; rerun with
  `--resume`.
- If an update reports a conflict, re-enrich that owner and reapply the intended
  edit to the fresh JSON rather than forcing an overwrite.
- Use the default visible browser during initial validation. Add `--headless`
  only after the login and iframe flows have been confirmed locally.
