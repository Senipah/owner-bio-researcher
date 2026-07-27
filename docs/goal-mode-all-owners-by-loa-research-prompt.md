# Goal Mode prompt: all owners in LOA-prioritised tranches

Use this prompt after the full details-and-socials enrichment has completed.
It researches the complete owner file in resumable, LOA-prioritised tranches
and produces review artifacts only. It does not approve research or update the
live system.

The prompt below processes the next 50 owners whose dossiers are absent,
invalid, or stale. Change `TRANCHE_SIZE = 50` to another positive number when
you want a different tranche size. Reuse the same prompt for every tranche.

## Prompt

Use `$research-owner-biography`.

Set `TRANCHE_SIZE = 50`.

The overall cohort is every owner in
`output/owners-list.vessel-enriched.enriched.json`, prioritised by largest
current-vessel LOA. Fully ranked owners come first from largest to smallest;
owners without a ranked current vessel remain in the cohort after them. This
run must research only the next `TRANCHE_SIZE` owners in that complete cohort
who do not already have a valid, current dossier.

Use `output/owner-research/all-by-loa/cohort.json` as the immutable
cohort manifest.

At the start:

1. Load `output/owners-list.vessel-enriched.enriched.json`.
2. If the cohort manifest does not exist, call
   `src.research_batch.select_research_owners(document, "all-by-loa", None)`
   and save a manifest containing:
   - the normalized source path;
   - the source file's SHA-256 hash;
   - selection `all-by-loa`, no limit, and the total cohort size;
   - creation timestamp; and
   - every owner in order, each with cohort position, `person_id`, display
     name, ranking status, `loa_rank`, `largest_current_loa_m`, and
     largest-current vessel name.
3. If the manifest exists, reuse its ordered person IDs. Do not regenerate or
   reorder it. Verify that the current input contains the same owners and LOA
   values. If the source hash changed, revalidate every existing dossier
   against the current input and report the change. Stop for user direction
   if cohort membership or LOA ordering changed.
4. Confirm every cohort owner has:
   - `enrichment.status=ok`;
   - `workflow.owner_details_enriched=true`;
   - a populated `details` object; and
   - `person_id` and `profile_url`.
5. Confirm owners marked `vessel_ownership.ranking_status=ranked` have both
   `loa_rank` and `largest_current_loa_m`. Preserve owners without a ranked
   current vessel after the fully ranked group; do not drop or replace them.
6. Do not substitute Top-100 rank, array position, gross tonnage, fame, net
   worth, or editorial judgment for the frozen cohort.

Inventory the dossier directory before assigning research. Treat an existing
dossier as complete only when:

- its person ID belongs to the frozen cohort;
- it is schema version 4; and
- this exact command succeeds:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.vessel-enriched.enriched.json
```

An absent, invalid, or stale dossier is pending regardless of its filename or
claimed status. Order pending owners by their frozen cohort position, select
the first `TRANCHE_SIZE`, print that tranche's positions, person IDs, names,
vessels, and LOAs, and research exactly that selection in this run. Do not
skip a difficult owner in favour of a later one. If fewer than
`TRANCHE_SIZE` remain, process all remaining owners. If none remain, skip
research and compile the final complete-cohort review artifacts.

For the selected tranche, produce one schema-v4 dossier per owner beneath
`output/owner-research/all-by-loa/`. Every dossier must contain:

1. validated, evidence-backed short and longer biographies;
2. `primary_industry`, `wealth_origin`, and `wealth_relationship`
   classifications;
3. an explicit Forbes result;
4. an inventory of missing details and supported link types;
5. only confidence-85-or-higher proposed details and links; and
6. `review.status=pending`.

Use a bounded worker pool of at most three research subagents. Give each
subagent exactly one owner at a time and `$research-owner-biography`. When a
subagent finishes, the main agent must validate its dossier before assigning
that worker another owner. Do not allow subagents to edit the shared owner
JSON, cohort manifest, source code, skill files, or another owner's dossier.
The main agent owns cohort selection, identity review, validation,
cross-owner consistency, checkpoint tracking, and compilation.

For every selected owner:

- run `inventory_owner.py` against the exact enriched input and person ID;
- resolve identity using name, public role or business, geography, family, and
  yacht context before collecting facts;
- search Forbes first and record `verified`, `not_found`, `ambiguous`, or
  `unavailable`;
- classify industry, wealth origin, and wealth relationship independently
  using `references/wealth-classification.md`;
- explain how wealth or prominence arose rather than foregrounding net worth;
- search supported person-relevant social types, prioritising Instagram,
  LinkedIn, and Personal Website;
- reject namesake, company, fan, family-member, and uncorroborated accounts;
- use a distinct Company Website proposal only when official evidence connects
  the person to the company;
- keep lower-confidence facts and links in review candidates or uncertainties;
- draft a neutral 50-55 word short biography and a standalone,
  two-paragraph longer biography of 90-190 words, preferably 120-170;
- use the longer biography for the formative route, an important turning
  point, and one or two strongly sourced layers of character colour, later
  activity, or meaningful yachting context;
- do not pad sparse profiles, repeat the short text verbatim, append yacht
  names without a meaningful story, or infer character from ownership alone;
- save the dossier using the person ID in its filename;
- leave `review.status=pending`; and
- run the exact validation command above, fixing all failures before marking
  that owner complete.

If a record represents an institution, government, municipality, unresolved
placeholder, or otherwise is not a natural person, do not invent a human
identity or personal wealth story. Preserve its cohort position and record the
identity limitation explicitly under the research contract. Stop for user
direction only if a schema-valid, honest dossier cannot represent the record;
do not silently replace it with a later owner.

After the tranche validates, perform a main-agent consistency review across
all currently valid cohort dossiers:

- both biography tones, structures, and lengths match the Shahid Khan
  calibration;
- royal, sovereign, family, and personal wealth are not conflated, and an
  oil-producing state is not treated as evidence of personal `Energy` wealth;
- inherited, self-made, dynastic/royal, family-transfer, mixed, and unknown
  origin classifications are applied consistently;
- industry follows the principal identifiable private assets, while
  relationship distinguishes founders, operators, investors, heirs, family
  office principals, royal beneficiaries, custodians, and passive owners;
- proposed select values use labels supported by the owner form;
- social type IDs match the input lookup; and
- no dossier is approved on the user's behalf.

Find the largest contiguous prefix of the frozen cohort for which every
dossier validates. Let its size be `COMPLETED_PREFIX`. If it is greater than
zero, replace every `COMPLETED_PREFIX` placeholder below with that integer and
compile a cumulative checkpoint review:

```powershell
.\venv\Scripts\python.exe .\compile_owner_research.py `
  --input output\owners-list.vessel-enriched.enriched.json `
  --dossier-dir output\owner-research\all-by-loa `
  --selection all-by-loa `
  --limit COMPLETED_PREFIX `
  --output output\research-enriched-owners-list.all-by-loa.first-COMPLETED_PREFIX.json `
  --report output\research-enriched-owners-list.all-by-loa.first-COMPLETED_PREFIX.html
```

On the first run, `COMPLETED_PREFIX` should normally be 50, producing the
initial CEO review sample. If that sample is approved, rerun this same prompt;
the next tranche will normally be cohort positions 51-100 and the cumulative
checkpoint will contain the first 100 owners.

When every cohort dossier validates, use the full cohort size in the final
artifact filenames.

Acceptance criteria for this run:

- only the next requested tranche was researched;
- every newly completed dossier validates against the exact enriched input;
- all pre-existing valid dossiers remain unchanged unless validation required
  a repair;
- the compiled checkpoint contains exactly the valid contiguous LOA prefix;
- `_baseline`, `person_id`, `profile_url`, vessel ownership data, and existing
  `profile_key` values remain unchanged;
- pending output owners retain `workflow.ai_enriched=false`;
- the original enriched input hash is unchanged;
- nothing is applied to the live website; and
- the run stops after this tranche even when more cohort owners remain.

When the tranche is complete, return:

- the processed cohort positions, person IDs, names, vessels, and LOAs;
- new and cumulative valid-dossier counts;
- checkpoint JSON and HTML paths;
- validation failures, unresolved identities, and limited-evidence owners;
- the next pending cohort position and number remaining; and
- an explicit statement that all dossiers remain pending review and nothing
  was applied.

## After review

Approval is a separate task. For accepted dossiers, a human must set
`review.status=approved` plus `reviewed_by` and `reviewed_at`. Only then compile
an approved file with `--mark-ai-enriched`, run `update_owners.py` without
`--apply`, inspect its audit, and obtain separate authorisation before any live
apply. Dossiers marked `rejected` retain the original owner values and remain
ineligible for update.
