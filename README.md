# Owner Bio Researcher

This toolkit exports the complete Superyacht Network owner report, enriches
each owner with every editable details field and social-media link, and safely
applies reviewed JSON changes back through the website's edit overlays.

The normal workflow is:

1. Export the owner list.
2. Enrich the export.
3. Edit a copy of the enriched JSON.
4. Run an update dry-run and inspect its audit report.
5. Test the update flow on a dedicated dummy person.
6. Apply the reviewed changes.

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

## 2. Enrich owner details and social profiles

```powershell
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.json
```

The default output is `output\owners-list.enriched.json`. Every named editable
control in the details form is represented, including blank fields. Selects
retain both their visible value and internal option ID. Internal notes and
biography are stored as HTML because the site uses CKEditor.

An interrupted run can resume from its existing output:

```powershell
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.json `
  --output output\owners-list.enriched.json `
  --resume
```

Targeted and diagnostic runs:

```powershell
# Re-fetch a specific person
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.enriched.json `
  --output output\one-owner.enriched.json `
  --person-id 8690 `
  --refresh

# Process at most ten eligible records
.\venv\Scripts\python.exe .\enrich_owners.py `
  --input output\owners-list.json `
  --limit 10
```

Each owner records `pending`, `ok`, or `error`. Failures do not discard
successful checkpoints.

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

## 3. Preview and apply updates

Always start with a dry-run:

```powershell
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.enriched.json
```

Audit reports are written beneath `output\audits`. Review planned changes,
skipped blanks, and conflicts before applying:

```powershell
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.enriched.json `
  --person-id 8690 `
  --apply
```

Potentially destructive options are separate and explicit:

```powershell
# Permit edited blank values to clear live fields
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.enriched.json `
  --person-id 8690 `
  --allow-clear `
  --apply

# Also remove live social profiles absent from the JSON array
.\venv\Scripts\python.exe .\update_owners.py `
  --input output\owners-list.enriched.json `
  --person-id 8690 `
  --replace-socials `
  --apply
```

After an apply run, continue future editing from the generated
`*.applied-<timestamp>.json` file because it contains the verified current
baseline.

## 4. Reversible dummy-account test

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
