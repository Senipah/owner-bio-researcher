# Goal Mode prompt: all owners in LOA-prioritised tranches

Use this prompt after the full details-and-socials enrichment has completed.
It researches the complete owner file in resumable, LOA-prioritised tranches
and produces review artifacts only. It does not approve research or update the
live system.

The prompt below processes the next 50 owners whose dossiers are absent,
invalid, or stale. Change `TRANCHE_SIZE = 50` to another positive number when
you want a different tranche size. Reuse the same prompt for every tranche.
Schema-v5 dossiers are intentionally stale under the current editorial
contract; reuse their verified research and source ledgers where sound, but
rebuild their brief, biographies, and editorial assessment as schema v6.

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
- it is schema version 6; and
- this exact command succeeds:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\validate_dossier.py `
  DOSSIER_PATH `
  --owner-input output\owners-list.vessel-enriched.enriched.json `
  --strict-editorial
```

An absent, invalid, or stale dossier is pending regardless of its filename or
claimed status. Order pending owners by their frozen cohort position, select
the first `TRANCHE_SIZE`, print that tranche's positions, person IDs, names,
vessels, and LOAs, and research exactly that selection in this run. Do not
skip a difficult owner in favour of a later one. If fewer than
`TRANCHE_SIZE` remain, process all remaining owners. If none remain, skip
research and compile the final complete-cohort review artifacts.

For the selected tranche, produce one schema-v6 dossier per owner beneath
`output/owner-research/all-by-loa/`. Every dossier must contain:

1. `record_type=person`, `institution`, or `unresolved_placeholder`;
2. an unordered, source-hidden `biography_brief` fact pool with at least two
   distinct opening options, plus validated short and longer biographies and
   `editorial_assessment` for a person, or a non-applicable `editorial_note`
   and null biography/editorial fields for a non-person record;
3. `primary_industry`, `wealth_origin`, and `wealth_relationship`
   classifications;
4. an explicit Forbes result;
5. an inventory of missing details and supported link types;
6. only confidence-85-or-higher proposed details and links; and
7. `review.status=pending`.

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
- complete all research before drafting and build the schema-v6
  `biography_brief` as an unordered editorial fact pool containing durable
  identity, defining work, nullable formative context and decisive moment, one
  to three enduring dimensions, optional character detail, at least two
  fact-level opening options with distinct modes, transient exclusions, and
  source IDs;
- never use the schema-v5
  `wealth_or_prominence_route`/`turning_point`/`later_chapter` outline, and
  explicitly exclude source publishers, confidence language, classification
  deliberation, vessel context, ranking, net worth, and transient figures from
  the brief;
- perform a separate editorial pass from that fact pool, deliberately select
  and record one opening mode and narrative shape, then reverse-check every
  material claim against the full source ledger;
- draft a neutral 50-55 word short biography and a standalone,
  two-paragraph longer biography of 90-190 words without targeting a preferred
  midpoint;
- treat the longer biography as a standalone edited profile, not an expanded
  answer to how wealth began; orient the reader through the person's defining
  identity, achievement, institution, asset, consequential decision,
  inherited responsibility, or public contribution;
- use a formative episode as the opening only when its relevance is immediately
  clear, and never open with abstract scaffolding such as "route into
  business", "path to wealth", "career began", "commercial footing", or
  "gave them their start";
- allow paragraph two to deepen the core work instead of forcing a later
  investment, sport, or philanthropy slot; include a second domain only when it
  genuinely distinguishes the person;
- end on a concrete fact, role, decision, or consequence, never a synthetic
  tie-back using "linking", "extending the same approach", "the arc",
  "second strand", "second thread", or equivalent phrasing;
- keep publisher names, source attribution, evidence gaps, confidence,
  classification reasoning, database language, and research-process narration
  out of both biographies;
- keep public-versus-private asset analysis in dossier metadata; for royal and
  dynastic owners, describe verified formation, succession, public work,
  interests, and influence without contrasting them against commercial
  enterprise, entrepreneurship, or personal wealth;
- use British English, no more than two explicit years, no more than one
  monetary or percentage figure, normally no sentence over 30 words, and no
  inventory of more than three representative companies, investments,
  offices, or institutions;
- vary openings, paragraph transitions, rhythms, and endings against
  `references/editorial-calibrations.md`; vary both opening mode and narrative
  shape, and do not default to birthplace, career-entry chronology, “His
  later...”, or a concluding wealth-classification verdict;
- treat current-vessel relationships and LOA rank as selection and identity
  context only, never as a reason to mention a vessel in either biography;
- apply the sale-independence test: both biographies must remain accurate,
  coherent, and complete if the owner sells every current vessel tomorrow;
- never use vessel names, dimensions, builders, delivery dates, commissions,
  or ownership histories as biography colour; independently significant
  maritime careers or sustained competitive, research, or philanthropic work
  may be described only by focusing on the enduring activity;
- do not pad sparse profiles or repeat the short text verbatim;
- save the dossier using the person ID in its filename;
- leave `review.status=pending`; and
- run the exact validation command above, fixing all failures before marking
  that owner complete.

If a record represents an institution, government, municipality, unresolved
placeholder, or otherwise is not a natural person, do not invent a human
identity or personal wealth story. Set the appropriate non-person
`record_type`, leave `biography_brief`, `biography`, and `long_biography` null,
populate `editorial_note`, and make no personal detail or social proposals.
Preserve its cohort position; do not silently replace it with a later owner.

After the tranche validates, perform a main-agent consistency review across
all currently valid cohort dossiers:

- biographies meet the seven-part editorial rubric and use the complete
  calibration set without copying one structure across the tranche;
- published prose contains no source narration, classification deliberation,
  negative wealth-taxonomy contrasts, database/process language, or repeated
  AI-style conclusions;
- both biographies pass the sale-independence test and contain no vessel fact
  introduced from the LOA-ranked owner relationship;
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

Then perform a dedicated cross-owner editorial pass over the selected tranche.
Create a working table containing owner, opening mode, narrative shape, first
sentence, paragraph-two opening, and final sentence. Use it to revise semantic
repetition even where exact wording differs. No single opening mode or
narrative shape may dominate business profiles, origin-story openings must be
a minority, and formulaic later-chapter transitions or synthetic tie-back
conclusions must be exceptional. This table is working review material and
does not need to be saved.

Run the tranche-level editorial audit and revise all issues before compiling:

```powershell
.\venv\Scripts\python.exe `
  .agents\skills\research-owner-biography\scripts\audit_biography_corpus.py `
  output\owner-research\all-by-loa `
  --strict
```

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
- every schema-v6 person dossier passes the strict corpus editorial audit;
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
