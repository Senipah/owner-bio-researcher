# Project Context

## What this project does

Owner Bio Researcher is a Python 3.12 command-line toolkit for a staged
Superyacht Network data workflow:

1. Export the complete vessel-owner report.
2. Export the filtered YB Top 100 vessel report and inspect each vessel's
   Ultimate Beneficial Owners in edit mode without saving.
3. Mark current Top-100 owners for priority processing.
4. Enrich selected owners with every details-form field and social profile.
5. Compile confidence-scored AI research dossiers into a separate desired
   owner JSON and human-readable review report.
6. Preview and then apply safe, conflict-aware updates.

The human-facing commands and file lineage are maintained in `README.md`.

## Runtime architecture

| Concern | Source of truth | Runtime behavior |
| --- | --- | --- |
| Login/session | `src/auth.py` | SeleniumBase logs in, then copies browser cookies into an in-memory `requests.Session`. |
| URLs/timeouts | `src/constants.py` | Central SYN endpoints, schema version, and wait/request timeouts. |
| Owner report | `export_owners.py`, `src/parsers.py` | Requests fetches pages; Beautiful Soup parses rows and pagination. |
| Top-100 report | `mark_top_100_owners.py`, `src/top_100.py` | Requests exports the report; Selenium clicks the specification edit link and reads the UBO fieldset. |
| Owner vessel ranking | `enrich_owner_vessels.py`, `src/owner_vessels.py`, `src/parsers.py` | Requests reads owner UBO relationships, caches distinct vessel specifications, normalizes LOA to metres, and ranks a derived owner document. |
| Owner enrichment | `enrich_owners.py`, `src/enrichment.py`, `src/parsers.py` | Authenticated HTTP reads dynamically discover details controls and social profiles. |
| AI research compilation | `compile_owner_research.py`, `src/research_batch.py` | Selects owners explicitly by current Top-100 rank, fully ranked largest current-vessel LOA, or the complete owner file prioritised by LOA, validates independent dossiers, compiles high-confidence proposals into a separate JSON, and renders an HTML review report. |
| Change planning | `src/diffing.py` | Compares baseline, desired JSON, and current live state. |
| Live writes | `update_owners.py`, `src/browser_update.py` | Selenium opens edit overlays, waits for the iframe/form, writes selected fields, saves, and verifies by re-export. |
| Persistence | `src/io_utils.py` | Versioned JSON and atomic replacement checkpoints. |
| Workflow flags | `src/workflow.py` | Backfills and transitions Top-100, enrichment, AI, and system-update booleans. |

Read-only bulk work uses the authenticated HTTP session for speed. Browser
automation remains active for Top-100 edit-mode inspection and all owner
writes because those flows depend on interactive pages and iframe overlays.

## Owner document

Owner files use `schema_version: 1`. The top-level object contains:

- `exported_at`: UTC timestamp.
- `source`: report URL, pagination/count metadata, and warnings.
- `lookups.social_media_types`: social type ID-to-label mapping.
- `owners`: owner records keyed operationally by integer `person_id`.

Important owner fields:

- `report`: values captured from the list report.
- `details`: every named editable control, including blanks. Each entry
  preserves `label`, `kind`, and `value`; selects also preserve option IDs and
  labels, and rich text is HTML.
- `social_media_profiles`: stable `profile_key`, `type_id`, display `type`, and
  `url`.
- `_baseline`: deep copies of details and socials at enrichment or verified
  refresh time. This is the optimistic-concurrency reference and is not a
  desired-data editing surface.
- `enrichment`: `pending`, `ok`, or `error`, timestamp, and error text.
- `workflow`: `is_top_100_owner`, `owner_details_enriched`, `ai_enriched`, and
  `updated_in_system`.
- `top_100`: current/historical markers and all matched vessel relationships.
- `vessel_ownership` (optional): read-only all-fleet relationship scan,
  per-vessel normalized specifications, largest-known current vessel,
  `ranking_status`, and LOA rank.
- `ai_research` (optional, compiled research output): dossier path and review
  metadata, short and longer biography objects, plus evidence-backed
  `wealth_creation_industry`, `primary_industry`, `wealth_origin`, and
  `wealth_relationship` classifications. The two industry fields share one
  dictionary but independently describe the sector that created the original
  fortune and the current principal private interests. These are retained even
  before equivalent editable fields exist on the website. When
  `details.long_biography` is present, compilation maps the longer CKEditor
  HTML into that field.

Vessel-enriched owner documents may also contain a top-level
`vessel_specifications` cache keyed by vessel ID and a `vessel_enrichment`
summary. Raw LOA is retained alongside metric `loa_m`; imperial values are
converted at exactly 0.3048 metres per foot. Gross tonnage is captured when
present but does not control the default ranking.

The research compiler defaults to `--selection top-100`. Its explicit
`--selection largest-loa` mode accepts only owners whose
`vessel_ownership.ranking_status` is `ranked`, orders them by `loa_rank`, and
then applies `--limit` as an exact owner count. Incomplete vessel scans are
excluded rather than placed below fully ranked owners. The
`--selection all-by-loa` mode supports cumulative whole-file research: it
places those fully ranked owners first, then retains every remaining owner
after them, and applies `--limit` to that complete ordering.

Existing schema-v1 exports are accepted. `src/workflow.py` backfills missing
additive workflow fields in memory.

## Top-100 vessel document

`output/top-100-vessels.json` is a separate schema-v1 document with
`dataset: "top_100_vessels"`. It contains source/page/count diagnostics and
one record per ranked vessel:

- identifiers, name, builder, specification/edit URLs, and all report fields;
- `ownership_scan` with `pending`, `ok`, or `error` state;
- every current and historical UBO relationship.

A blank relationship `to` value defines current ownership. Only current
relationships set `workflow.is_top_100_owner=true`; ended relationships remain
discoverable through `top_100.historical_owner` and the relationship list.
Person IDs absent from the supplied owner export stay in the vessel data and
are reported as unmatched.

## State and reconciliation model

The updater treats owner JSON as three states:

```text
baseline (last export) -> desired (edited file)
          |
          +------------> live (re-read immediately before save)
```

- Desired equals baseline: no requested change.
- Live equals desired: the change is already present.
- Live equals baseline: the requested change may be applied.
- Live differs from both: conflict; skip rather than overwrite.

Blank desired values are skipped unless `--allow-clear` is set. Social
additions and baseline-keyed replacements are normal changes; removals require
`--replace-socials`. After a save, the updater re-exports the owner and only
then creates a new baseline and marks the record updated.

Workflow transitions are intentionally narrow:

- Top-100 annotation maintains `is_top_100_owner`.
- Successful details/social enrichment sets `owner_details_enriched=true`.
- Research compilation keeps `ai_enriched=false` unless
  `--mark-ai-enriched` is used. A strictly validated dossier with
  `review.status=complete` (or legacy `approved`) may then set it true and
  resets `updated_in_system=false` when it introduces desired changes. Only
  values with confidence 70 or higher are imported.
- Only a verified live apply sets `updated_in_system=true`.

## Storage and sensitive data

- Generated data, audits, screenshots, and dummy-test artifacts belong under
  `output/`, which is ignored by Git.
- `src/user_secrets.py` loads `SYN_USER` and `SYN_PASS`; credentials must not
  appear in JSON, logs, tests, or documentation.
- Saved HTML in `examples/` is intentionally ignored and can contain real
  system data. Do not commit it.
- JSON checkpoints use a temporary sibling file, `fsync`, and `os.replace` so
  interrupted runs do not leave a partially written destination.

## Testing signal and known gaps

The offline suite covers:

- owner-report, details-form, social-form, Top-100 report, and UBO parsing;
- pagination/filter preservation and current-versus-historical annotation;
- atomic JSON round trips and workflow backfill/transitions;
- blank policy, social merge/replacement, stale-live conflicts, and no-op
  detection.

Known constraints:

- Parser fixture tests require the local ignored `examples/` tree and will fail
  in a clean clone where those snapshots are absent.
- Browser login, overlay, CKEditor, and save selectors can change independently
  of the fixtures. Use a headed smoke test after selector changes.
- There is no offline end-to-end browser test. Use
  `test_dummy_account.py --person-id ID --apply` only with a dedicated dummy
  and inspect restoration artifacts.
- AI research remains agent-driven, while dossier validation, confidence-gated
  JSON compilation, automatic completion gating, and HTML reporting are
  implemented locally.
