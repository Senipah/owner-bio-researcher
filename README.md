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
The prompt freezes every owner in a single LOA-prioritised cohort, revalidates
existing dossiers, researches only the next configurable tranche, and writes a
cumulative review report after each run. Its default tranche size is 50, so the
first run produces owners 1-50 for review and the next approved run continues
with owners 51-100.

The JSON retains each owner's immutable `_baseline`, contains only the selected
owners, and applies only dossier proposals with confidence 85 or higher.
Pending research remains `workflow.ai_enriched=false`, so it cannot be selected
by the normal `--ai-enriched-only` update command.

For an editorial repair batch, add `--compare-dossier-dir` to render the
earlier and current short and long biographies side by side for every owner
whose biography text changed. The comparison directory is read only and does
not affect the compiled owner JSON:

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



```
Use `$research-owner-biography`.

Goal: research and complete exactly cohort positions 51–100 from the immutable LOA-prioritised owner cohort, then compile cumulative pending-review artifacts for positions 1–100.

Do not mark this goal complete until every acceptance criterion below is satisfied. Do not mark it blocked merely because the frozen first 50 contain the already authorised baseline editorial findings.

## Authoritative files

- Owner input:
  `output/owners-list.vessel-enriched.enriched.json`
- Immutable cohort:
  `output/owner-research/all-by-loa/cohort.json`
- Dossier directory:
  `output/owner-research/all-by-loa/`
- First-50 migration and baseline-exception record:
  `output/owner-research/all-by-loa-schema-v7-migration-summary.json`
- Existing cumulative first-50 artifacts:
  `output/research-enriched-owners-list.all-by-loa.first-50.json`
  `output/research-enriched-owners-list.all-by-loa.first-50.html`

Read the repository `AGENTS.md`, `README.md`, relevant AI documentation, and the complete `$research-owner-biography` skill and its required references before acting.

## Preflight

1. Verify that the migration summary records:

   - 50 migrated schema-v7 dossiers;
   - 50 structured-diff passes;
   - zero migration-related validation failures;
   - 23 frozen first-50 strict-validation failures;
   - 27 inherited first-50 corpus-audit findings;
   - `status.compilation_status` equal to
     `completed_with_authorised_baseline_editorial_exception`;
   - 50 compiled owners;
   - all compiled owners still having `workflow.ai_enriched=false`.

2. Verify the immutable cohort contains 4,197 owners and that its source hash is:

   `4477729a535d9cdf216efa7155a6a7ed0aae4ddf1c5e554b46f856aaf7f2a346`

   A different normalized source path is acceptable only if the content hash and cohort membership are unchanged.

3. Confirm the tranche boundaries:

   - position 51: person ID `7440`, Yusaku Maezawa, Nausicaä, 114.2 m;
   - position 100: person ID `790`, Robert Friedland, Luna, 90.0 m.

   Stop for user direction if the cohort membership, ordering, IDs, or LOA values have changed.

4. Record SHA-256 hashes for:

   - every dossier at cohort positions 1–50;
   - the cohort manifest;
   - the enriched owner input;
   - the existing first-50 compiled JSON and HTML.

5. Inventory positions 51–100. This run is resumable:

   - reuse a dossier only if it belongs to the correct cohort owner, is schema v7, and passes strict validation against the exact owner input;
   - treat absent, stale, mismatched, or invalid dossiers as pending;
   - preserve a backup of any existing invalid partial dossier before replacing it;
   - never substitute an owner from position 101 or later.

6. Do not modify any dossier from positions 1–50. Their biography and editorial findings are frozen. The authorised exception applies only to their already recorded validation and corpus-audit debt and only permits cumulative compilation.

## Research scope

Research every owner at positions 51–100 whose dossier is not already valid. Complete the whole fixed tranche even when an identity is difficult or the public record is sparse. Do not skip an owner in favour of a later one.

Use a bounded pool of at most three research subagents. Give each subagent exactly one owner at a time and instruct it to use `$research-owner-biography`. The main agent owns cohort selection, validation, cross-owner review, integrity checks, and compilation. Validate each returned dossier before assigning that worker another owner.

Subagents may edit only their assigned owner’s dossier. They must not edit the owner input, cohort, first-50 dossiers, source code, documentation, skill files, compiled artifacts, or another owner’s dossier.

For each owner:

1. Run the skill’s inventory script against the exact enriched input and person ID.
2. Resolve identity using business role, geography, family context, and the vessel relationship only as identity evidence.
3. Research using the skill’s source hierarchy and maintain a complete source ledger.
4. Perform the explicit Forbes check and record the supported result.
5. Classify these four fields independently:

   - `wealth_creation_industry`
   - `primary_industry`
   - `wealth_origin`
   - `wealth_relationship`

6. Apply the industry distinction carefully:

   - `wealth_creation_industry` is the durable sector that principally created the fortune;
   - `primary_industry` is the sector that best describes the person’s principal identifiable interests at the time of research;
   - use the exact shared label `Cryptocurrency` when reliable evidence establishes that crypto principally created the fortune, even if the person subsequently diversified;
   - examples may be described in the biography as an early Bitcoin investor, protocol creator, exchange founder, or similar, but do not create additional flags;
   - do not classify someone as Cryptocurrency merely because they later invested in tokens, accepted crypto payments, promoted a project, or hold crypto in a diversified portfolio;
   - a diversified former crypto entrepreneur may therefore have `wealth_creation_industry=Cryptocurrency` and a different `primary_industry`;
   - use `Unknown` when the classification cannot be supported confidently. Every non-Unknown classification requires confidence of at least 85.

7. Research supported person-specific social profiles and reject namesake, company-only, fan, family-member, or uncorroborated accounts.
8. Complete research before writing. Build the schema-v7 unordered `biography_brief` and perform a separate editorial pass.
9. For a person, produce:

   - a neutral 50–55 word short biography;
   - a standalone 90–190 word long biography in exactly two paragraphs;
   - a complete `editorial_assessment`;
   - no more than two shared short/long anchors;
   - at least one short-only dimension;
   - at least two substantive long-only dimensions.

10. Follow the complete biography-style and editorial-calibration requirements:

    - British English;
    - source attribution and research narration stay out of published prose;
    - the long biography must not be an expanded or reordered short biography;
    - vary opening modes, narrative shapes, transitions, rhythms, and endings across the tranche;
    - avoid formulaic origin-story openings, later-chapter transitions, synthetic tie-backs, and classification verdicts;
    - apply the sale-independence test;
    - do not mention vessel names, dimensions, builders, deliveries, commissions, or ownership histories merely because they appear in the input;
    - do not pad sparse profiles.

11. For a genuine institution or unresolved non-person record, use the schema-v7 non-person path. Do not invent a person, biography, personal fortune, or social proposals.
12. Leave `review.status=pending`. Do not approve any dossier on the user’s behalf.

## Per-owner validation

Every dossier at positions 51–100 must pass this exact command:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.vessel-enriched.enriched.json `
  --strict-editorial
```

Fix all errors and warnings for positions 51–100. The first-50 exception must never be extended to a new dossier.

## Tranche and cumulative editorial validation

After all 50 dossiers validate:

1. Perform a main-agent cross-owner review of positions 51–100 using a working table containing owner, opening mode, narrative shape, first sentence, paragraph-two opening, and final sentence.

2. Create a temporary directory containing only the dossiers for positions 51–100 and run:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py `
  TEMP_TRANCHE_DIRECTORY `
  --strict
```

Revise the new dossiers until this tranche-only strict audit passes with zero issues.

3. Run the corpus auditor over the cumulative first 100 dossiers. Compare its output with the 27 inherited findings stored in the migration summary.

   - The only permitted unresolved findings are exact inherited findings involving only frozen positions 1–50.
   - Fix every finding involving a position 51–100 owner by editing only the new owner’s dossier.
   - Fix every new cross-owner repetition involving the new tranche.
   - If a genuinely new finding involving only frozen positions 1–50 appears, preserve the first 50 and report it rather than silently expanding the exception.
   - Do not interpret the inherited 23 validation failures or 27 audit findings as evidence that this goal is blocked.

## Cumulative compilation

Compile cumulative pending-review artifacts for exactly positions 1–100:

- `output/research-enriched-owners-list.all-by-loa.first-100.json`
- `output/research-enriched-owners-list.all-by-loa.first-100.html`

The normal `compile_owner_research.py` CLI will reject the inherited first-50 editorial failures because it applies strict validation to every selected dossier. Do not weaken or modify that CLI.

Use the already authorised baseline exception through a temporary one-off Python process that calls the normal repository functions directly:

- `src.io_utils.load_json`
- `src.research_batch.load_dossiers`
- `src.research_batch.compile_research_batch`
- `src.research_batch.render_research_report`
- `src.io_utils.atomic_write_json`
- `src.io_utils.atomic_write_text`

Use:

- selection `all-by-loa`;
- limit `100`;
- `mark_ai_enriched=False`;
- the exact enriched owner input and dossier directory.

Do not attach biography comparisons because the comparison backup covers only the first 50.

Before bypassing the CLI validation gate, independently prove that:

- all positions 51–100 pass strict validation;
- the tranche-only audit passes;
- the cumulative audit contains no unresolved issues beyond the recorded first-50 baseline;
- all first-50 dossier hashes remain unchanged;
- all 100 selected dossiers are schema v7 and correspond to the frozen cohort;
- all reviews remain pending.

After compilation, verify:

- exactly 100 owners were compiled in cohort order;
- the first and last IDs are the expected position-1 and position-100 IDs;
- every compiled owner has `workflow.ai_enriched=false`;
- every compiled `ai_research` object contains all four classification fields;
- the first-50 biographies, classifications, proposals, and protected owner values match the existing first-50 compiled artifact, allowing only regenerated compilation timestamps and cumulative batch metadata;
- `_baseline`, `person_id`, `profile_url`, vessel ownership data, and existing `profile_key` values remain unchanged.

## Tranche summary

Write:

`output/owner-research/all-by-loa-tranche-51-100-summary.json`

Include:

- schema version and timestamps;
- cohort range and exact owner list with positions, IDs, names, vessels, and LOAs;
- newly created, resumed, and already-valid dossier counts;
- per-owner strict-validation results;
- identity conflicts, unresolved identities, and limited-evidence owners;
- all four classifications and confidence scores;
- Cryptocurrency count and named owners;
- Unknown counts by classification;
- source and Forbes-result summaries;
- tranche-only audit result;
- cumulative audit result;
- the exact inherited first-50 findings permitted by the authorised exception;
- confirmation that no new owner used the exception;
- preflight and final hashes for protected inputs and first-50 dossiers;
- compiled artifact paths, owner counts, and SHA-256 hashes;
- next pending cohort position and remaining owner count.

## Safety constraints

- Never overwrite the enriched owner input or cohort manifest.
- Never modify positions 1–50.
- Do not edit source code, documentation, tests, or skills.
- Do not approve dossiers.
- Do not run `update_owners.py`.
- Do not perform any live website write.
- Do not commit generated research output.
- Do not begin position 101.

## Acceptance criteria

The goal is complete only when:

- positions 51–100 all have schema-v7 dossiers;
- all 50 pass strict per-owner validation;
- the position-51–100 strict corpus audit passes;
- cumulative audit debt is limited to the exact authorised first-50 baseline;
- all first-50 dossier hashes are unchanged;
- cumulative first-100 JSON and HTML artifacts exist and contain exactly 100 owners;
- every dossier remains pending and every compiled owner has `workflow.ai_enriched=false`;
- the owner input and cohort hashes are unchanged;
- the tranche summary exists;
- nothing was applied live;
- processing stopped before position 101.

The expected next pending position after successful completion is 101, with 4,097 owners remaining in the frozen cohort.

Return a concise final report containing:

- processed positions and owner count;
- new, resumed, and cumulative dossier counts;
- validation and audit results;
- Cryptocurrency and Unknown classification counts;
- unresolved or limited-evidence owners;
- cumulative artifact paths and hashes;
- confirmation that the first 50 remained frozen;
- the next pending position and remaining count;
- confirmation that all reviews remain pending, nothing was committed, and nothing was applied live.

```

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
